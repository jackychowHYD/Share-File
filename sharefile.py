import streamlit as st
import boto3
from botocore.config import Config
import urllib3
import os

# 關閉 SSL 驗證警告 / Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. 頁面配置 / Page Configuration
# ==========================================
st.set_page_config(
    page_title="雲端報告管理平台 | Cloud Report Platform",
    page_icon="📂",
    layout="wide"
)

# ==========================================
# 2. 多使用者權限驗證系統 / Authentication System
# ==========================================
def check_authentication():
    # 讀取 Secrets 中的使用者列表 / Read user list from secrets
    try:
        users_db = st.secrets["USERS"]
    except Exception:
        users_db = {
            "admin": "admin123",
            "client_a": "passA123",
            "client_b": "passB123"
        }

    def login_action():
        username = st.session_state["login_user"].strip()
        password = st.session_state["login_pass"].strip()
        
        if username in users_db and users_db[username] == password:
            st.session_state["authenticated_user"] = username
            st.session_state["is_admin"] = (username == "admin")
            # 清除輸入框紀錄 / Clear inputs
            del st.session_state["login_user"]
            del st.session_state["login_pass"]
            st.session_state["login_error"] = False
        else:
            st.session_state["login_error"] = True

    # 檢查是否已登入 / Check if already authenticated
    if st.session_state.get("authenticated_user"):
        return True

    # 登入介面 / Login UI
    st.markdown("## 🔒 系統防護：請登入帳號 / System Access: Please Login")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.text_input("帳號 / Username", key="login_user")
        st.text_input("密碼 / Password", type="password", key="login_pass")
        st.button("登入系統 / Login", on_click=login_action, type="primary")
        
        if st.session_state.get("login_error"):
            st.error("❌ 帳號或密碼不正確！ / Invalid username or password!")
            
    return False

if not check_authentication():
    st.stop()

# 取得目前登入使用者資訊 / Get current user info
current_user = st.session_state.get("authenticated_user")
is_admin = st.session_state.get("is_admin", False)

# 側邊欄：顯示身分與登出 / Sidebar: Role Status & Logout
with st.sidebar:
    role_badge = f"👑 系統管理員 / Admin ({current_user})" if is_admin else f"👤 授權使用者 / User ({current_user})"
    st.write(f"目前登入 / Current User: **{role_badge}**")
    if st.button("🚪 登出系統 / Logout"):
        st.session_state["authenticated_user"] = None
        st.session_state["is_admin"] = False
        st.rerun()

st.title("📂 雲端報告管理平台 / Cloud Report Management Platform")

# ==========================================
# 3. 讀取與清理 ENDPOINT_URL / Setup Credentials
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

clean_endpoint = raw_endpoint.rstrip("/")
if clean_endpoint.endswith("id.r2.cloudflarestorage.com"):
    clean_endpoint = clean_endpoint.replace("id.r2.cloudflarestorage.com", ".r2.cloudflarestorage.com")

ENDPOINT_URL = clean_endpoint

# ==========================================
# 4. 初始化 R2 客戶端 / Initialize R2 Client
# ==========================================
@st.cache_resource
def get_r2_client():
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
        verify=False
    )

try:
    s3_client = get_r2_client()
except Exception as e:
    st.error(f"連線至 R2 儲存桶失敗 / Connection to R2 bucket failed: {e}")
    st.stop()

CATEGORIES = ["Inspection Report", "Audit Report", "Test Report", "Others"]

# 可指派的權限清單 / Assignable access options
ASSIGNABLE_USERS = ["All Users (公開 / Public)", "client_a", "client_b"]

# ==========================================
# 5. 動態分頁展示 / Dynamic Tabs
# ==========================================
if is_admin:
    tab_upload, tab_view = st.tabs(["📤 上傳檔案 / Upload File", "📁 瀏覽與下載報告 / View & Download Reports"])
else:
    tab_view_list = st.tabs(["📁 瀏覽與下載報告 / View & Download Reports"])
    tab_view = tab_view_list[0]
    tab_upload = None

# ------------------------------------------
# TAB 1: 檔案上傳 (僅 Admin) / File Upload (Admin Only)
# ------------------------------------------
if tab_upload is not None:
    with tab_upload:
        st.header("上傳檔案並指派權限 / Upload File & Assign Rights")
        
        col_cat, col_access = st.columns(2)
        with col_cat:
            selected_category = st.selectbox("1. 請選擇報告分類 / Select Category:", CATEGORIES)
        with col_access:
            assigned_access = st.selectbox("2. 指派可存取使用者 / Assign Access Right:", ASSIGNABLE_USERS)
            
        uploaded_file = st.file_uploader("選擇要上傳的 PDF 檔案 / Select PDF File", type=["pdf"])
        
        if st.button("開始上傳 / Start Upload", type="primary"):
            if uploaded_file is not None:
                access_prefix = "public" if "Public" in assigned_access or "公開" in assigned_access else assigned_access
                file_key = f"{selected_category}/{access_prefix}/{uploaded_file.name}"
                
                with st.spinner("檔案上傳中，請稍候... / Uploading file, please wait..."):
                    try:
                        s3_client.upload_fileobj(
                            uploaded_file,
                            BUCKET_NAME,
                            file_key,
                            ExtraArgs={"ContentType": "application/pdf"}
                        )
                        st.success(f"✅ 成功上傳 / Uploaded: [{uploaded_file.name}]，權限 / Rights: [{assigned_access}]")
                    except Exception as e:
                        st.error(f"❌ 上傳失敗 / Upload failed: {e}")
            else:
                st.warning("請先選擇要上傳的檔案！ / Please select a file first!")

# ------------------------------------------
# TAB 2: 瀏覽與下載 / Browse & Download
# ------------------------------------------
with tab_view:
    st.header("瀏覽與下載授權報告 / Browse & Download Authorized Reports")
    
    view_category = st.selectbox("篩選分類 / Filter Category:", CATEGORIES, key="view_cat")
    prefix_path = f"{view_category}/"
    
    try:
        response = s3_client.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix_path
        )
        objects = response.get("Contents", [])
        
        # 權限過濾 / Access Filtering
        accessible_files = []
        for obj in objects:
            key = obj["Key"]
            if key == prefix_path:
                continue
                
            path_parts = key.replace(prefix_path, "").split("/")
            if len(path_parts) >= 2:
                access_tag = path_parts[0]
                filename = "/".join(path_parts[1:])
            else:
                access_tag = "public"
                filename = path_parts[0]
            
            if is_admin or access_tag == "public" or access_tag == current_user:
                accessible_files.append({
                    "full_key": key,
                    "filename": filename,
                    "access_tag": access_tag,
                    "size_mb": round(obj["Size"] / (1024 * 1024), 2)
                })

        if not accessible_files:
            st.info(f"在 [{view_category}] 分類中，目前沒有您可存取的檔案。 / No accessible files in [{view_category}].")
        else:
            st.write(f"目前包含 **{len(accessible_files)}** 個可存取檔案 / Accessible Files Count: **{len(accessible_files)}**")
            
            for file_info in accessible_files:
                full_key = file_info["full_key"]
                filename = file_info["filename"]
                access_tag = file_info["access_tag"]
                file_size_mb = file_info["size_mb"]
                
                # Layout
                if is_admin:
                    col1, col2, col3 = st.columns([3, 1.5, 1])
                else:
                    col1, col2 = st.columns([3, 2])
                
                with col1:
                    tag_badge = f"`[{access_tag}]` " if is_admin else ""
                    st.markdown(f"📄 {tag_badge}**{filename}** `({file_size_mb} MB)`")
                
                with col2:
                    try:
                        presigned_url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={
                                'Bucket': BUCKET_NAME, 
                                'Key': full_key,
                                'ResponseContentType': 'application/pdf'
                            },
                            ExpiresIn=3600
                        )
                        st.markdown(
                            f'<a href="{presigned_url}" target="_blank" style="text-decoration:none;">'
                            f'<button style="background-color:#4CAF50; color:white; border:none; padding:6px 12px; border-radius:4px; cursor:pointer;">'
                            f'📥 下載 / 檢視 PDF (Download / View)</button></a>', 
                            unsafe_allow_html=True
                        )
                    except Exception as err:
                        st.error(f"連結產生失敗 / Failed to generate link: {err}")

                if is_admin:
                    with col3:
                        if st.button("🗑️ 刪除 / Delete", key=f"del_{full_key}"):
                            try:
                                s3_client.delete_object(Bucket=BUCKET_NAME, Key=full_key)
                                st.success(f"已刪除 / Deleted: {filename}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"刪除失敗 / Delete failed: {e}")
                                
                st.divider()

    except Exception as e:
        st.error(f"無法讀取數據 / Unable to fetch bucket data: {e}")