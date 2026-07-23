import os
import streamlit as st
import boto3

# ==================== 雲端物件儲存 (S3 / R2) 設定 ====================
import streamlit as st
import boto3

# 自動判斷是本地執行還是雲端執行
try:
    # 嘗試從 Streamlit Cloud 的 Secrets 讀取
    AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
    AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
    BUCKET_NAME = st.secrets["BUCKET_NAME"]
    ENDPOINT_URL = st.secrets["ENDPOINT_URL"]
    AWS_REGION = "auto"
except Exception:
    # 如果在本地沒有設定 st.secrets，則直接寫死在這邊方便本地測試
    AWS_ACCESS_KEY_ID = "93f1518eaabd36d90c660f68c15f17b3"
    AWS_SECRET_ACCESS_KEY = "18001ef32838fc1dc5b7d9a53e80c35d1fae03d590fe3eb188ea8a59fafaf5f4"
    BUCKET_NAME = "success-way"
    ENDPOINT_URL = "https://0fc5d82eb0dcef6539298f2c3221edea.r2.cloudflarestorage.com"
    AWS_REGION = "auto"

# 建立連接 Cloudflare R2 的客戶端
s3_client = boto3.client(
    's3',
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

# 初始化 S3 / R2 Client
@st.cache_resource
def init_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
        endpoint_url=ENDPOINT_URL
    )

s3 = init_s3_client()
# ====================================================================

# 更新後的 4 種報告分類
REPORT_CATEGORIES = ["Inspection Report", "Audit Report", "Test Report", "Others"]

PLATFORM_PASSWORD = "my_secure_password123"
FORBIDDEN_EXTENSIONS = (".exe", ".bat", ".php")

st.set_page_config(page_title="專業雲端報告管理平台", page_icon="📊", layout="centered")

st.title("📊 專業雲端報告管理平台")
st.write("安全管理您的四大類報告，檔案直接存放於 Cloudflare R2 雲端硬碟。")

# 1. 密碼驗證
password = st.text_input("請輸入平台存取密碼", type="password")

if not password:
    st.info("請先輸入密碼以解鎖平台功能。")
elif password != PLATFORM_PASSWORD:
    st.error("❌ 密碼錯誤，請重新輸入！")
else:
    st.success("✅ 密碼正確，歡迎使用！")
    st.divider()
    
    # 2. 檔案上傳區塊
    st.subheader("📤 上傳新報告至雲端")
    selected_category = st.selectbox("選擇報告類型 (Category)", REPORT_CATEGORIES)
    
    uploaded_file = st.file_uploader("選擇報告檔案 (建議 PDF 或文件格式)", type=["pdf", "docx", "xlsx", "zip", "txt"])
    
    if uploaded_file is not None:
        filename = uploaded_file.name
        
        if filename.lower().endswith(FORBIDDEN_EXTENSIONS):
            st.error(f"❌ 為了安全起見，不允許上傳此格式：{filename}")
        else:
            # 雲端儲存路徑 (Key)
            file_key = f"{selected_category}/{filename}"
            
            try:
                with st.spinner("正在上傳至雲端物件儲存..."):
                    s3.upload_fileobj(uploaded_file, BUCKET_NAME, file_key)
                st.success(f"🎉 成功上傳 [{selected_category}] 類別報告至雲端：{filename}")
            except Exception as e:
                st.error(f"❌ 上傳失敗: {e}")
    
    st.divider()
    
    # 3. 雲端報告清單與下載區塊
    st.subheader("📥 雲端報告清單與下載")
    
    tabs = st.tabs(REPORT_CATEGORIES)
    
    for i, category in enumerate(REPORT_CATEGORIES):
        with tabs[i]:
            try:
                response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f"{category}/")
                
                if "Contents" not in response:
                    st.info(f"目前雲端尚無 {category} 類別的報告。")
                else:
                    files = [obj['Key'] for obj in response['Contents'] if obj['Key'] != f"{category}/"]
                    
                    if not files:
                        st.info(f"目前雲端尚無 {category} 類別的報告。")
                    else:
                        for file_key in files:
                            file_name = file_key.split("/")[-1]
                            
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.text(file_name)
                            with col2:
                                if st.button("下載", key=file_key):
                                    try:
                                        file_obj = s3.get_object(Bucket=BUCKET_NAME, Key=file_key)
                                        file_data = file_obj['Body'].read()
                                        st.download_button(
                                            label=f"確認下載 {file_name}",
                                            data=file_data,
                                            file_name=file_name,
                                            key=f"dl_{file_key}"
                                        )
                                    except Exception as e:
                                        st.error(f"下載失敗: {e}")
            except Exception as e:
                st.error(f"無法讀取雲端檔案列表: {e}")