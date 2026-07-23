import streamlit as st
import boto3
from botocore.config import Config
import urllib3
import os

# 關閉 SSL 驗證警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. 頁面配置
# ==========================================
st.set_page_config(
    page_title="雲端報告管理平台",
    page_icon="📂",
    layout="wide"
)

# ==========================================
# 2. 密碼驗證系統
# ==========================================
def check_password():
    try:
        correct_password = st.secrets["APP_PASSWORD"]
    except Exception:
        correct_password = "admin123"

    def password_entered():
        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("## 🔒 系統防護：請先登入")
    st.text_input(
        "請輸入系統存取密碼", type="password", on_change=password_entered, key="password"
    )
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ 密碼不正確，請重新輸入。")
        
    return False

if not check_password():
    st.stop()

# 側邊欄登出按鈕
with st.sidebar:
    st.write("👤 已驗證權限")
    if st.button("🚪 登出系統"):
        st.session_state["password_correct"] = False
        st.rerun()

st.title("📂 雲端報告管理平台")
st.write("支援 Inspection Report、Audit Report、Test Report 與 Others 分類管理。")

# ==========================================
# 3. 讀取並自動修復 ENDPOINT_URL 與金鑰
# ==========================================
try:
    AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
    AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
    BUCKET_NAME = st.secrets["BUCKET_NAME"]
    raw_endpoint = st.secrets["ENDPOINT_URL"]
except Exception:
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "YOUR_ACCESS_KEY")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "YOUR_SECRET_KEY")
    BUCKET_NAME = os.environ.get("BUCKET_NAME", "success-way")
    raw_endpoint = os.environ.get("ENDPOINT_URL", "https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com")

# 自動清理：1. 去除結尾斜線 2. 自動修正 ID 結尾誤帶的 "id" 兩個字
clean_endpoint = raw_endpoint.rstrip("/")
if clean_endpoint.endswith("id.r2.cloudflarestorage.com"):
    clean_endpoint = clean_endpoint.replace("id.r2.cloudflarestorage.com", ".r2.cloudflarestorage.com")

ENDPOINT_URL = clean_endpoint

# ==========================================
# 4. 初始化 R2 客戶端 (修正 SSL 與 Addressing)
# ==========================================
@st.cache_resource
def get_r2_client():
    # 使用 path 模式，避免形成兩層子網域破壞 Cloudflare SSL 憑證
    r2_config = Config(
        region_name="auto",
        signature_version="s3v4",
        s3={"addressing_style": "path"}
    )
    
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        config=r2_config,
        verify=False  # 關閉權威機構憑證嚴格比對，直接通過握手
    )

try:
    s3_client = get_r2_client()
except Exception as e:
    st.error(f"連線至 R2 儲存桶失敗: {e}")
    st.stop()

CATEGORIES = ["Inspection Report", "Audit Report", "Test Report", "Others"]

# ==========================================
# 5. 主功能 Tabs
# ==========================================
tab_upload, tab_view = st.tabs(["📤 上傳檔案", "📁 瀏覽與下載報告"])

# ------------------------------------------
# TAB 1: 上傳
# ------------------------------------------
with tab_upload:
    st.header("上傳報告檔案")
    selected_category = st.selectbox("請選擇報告分類：", CATEGORIES)
    uploaded_file = st.file_uploader("選擇要上傳的 PDF 檔案", type=["pdf"])
    
    if st.button("開始上傳", type="primary"):
        if uploaded_file is not None:
            file_key = f"{selected_category}/{uploaded_file.name}"
            with st.spinner("檔案上傳中，請稍候..."):
                try:
                    s3_client.upload_fileobj(
                        uploaded_file,
                        BUCKET_NAME,
                        file_key,
                        ExtraArgs={"ContentType": "application/pdf"}
                    )
                    st.success(f"✅ 成功上傳檔案 [{uploaded_file.name}] 到分類 [{selected_category}]！")
                except Exception as e:
                    st.error(f"❌ 上傳失敗: {e}")
        else:
            st.warning("請先選擇要上傳的檔案！")

# ------------------------------------------
# TAB 2: 瀏覽與下載
# ------------------------------------------
with tab_view:
    st.header("瀏覽與下載已儲存的報告")
    view_category = st.selectbox("篩選分類：", CATEGORIES, key="view_cat")
    prefix_path = f"{view_category}/"
    
    try:
        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix_path
        )
        objects = response.get("Contents", [])
        files = [obj for obj in objects if obj["Key"] != prefix_path]
        
        if not files:
            st.info(f"分類 [{view_category}] 中目前沒有任何檔案。")
        else:
            st.write(f"目前包含 **{len(files)}** 個檔案：")
            for file_info in files:
                full_key = file_info["Key"]
                filename = full_key.replace(prefix_path, "")
                file_size_mb = round(file_info["Size"] / (1024 * 1024), 2)
                
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"📄 **{filename}** `({file_size_mb} MB)`")
                
                with col2:
                    try:
                        presigned_url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': BUCKET_NAME, 'Key': full_key},
                            ExpiresIn=3600
                        )
                        st.markdown(f"[🔗 點擊開啓/預覽]({presigned_url})")
                    except Exception as e:
                        st.write("無法產生預覽連結")

                with col3:
                    if st.button("🗑️ 刪除", key=f"del_{full_key}"):
                        try:
                            s3_client.delete_object(Bucket=BUCKET_NAME, Key=full_key)
                            st.success(f"已刪除 {filename}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"刪除失敗: {e}")
                st.divider()

    except Exception as e:
        st.error(f"無法讀取儲存桶資料: {e}")