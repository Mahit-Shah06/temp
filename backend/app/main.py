from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
import os, shutil, faiss, numpy as np, io
from sentence_transformers import SentenceTransformer

from app import models, schemas, crud, db, utils, classifier
from app.crud import LogCRUD, DocsCRUD
from app.encryption_logic import EncryptionHandler
from app.auth_logic import create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES

# -----------------------------
# Initializing values
# -----------------------------
# DB tables
models.Base.metadata.create_all(bind=db.engine)

# FastAPI app
app = FastAPI(title="AI Document Backend", version="1.0.0")

# Add CORS middleware for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Encryption handler
encryption = EncryptionHandler()

UPLOAD_DIR = "uploaded_docs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

search_model = SentenceTransformer('all-MiniLM-L6-v2')
documents_index = faiss.IndexFlatL2(384)
docid_map = {}

FAISS_INDEX_PATH = "faiss.index"
DOCID_MAP_PATH = "docid_map.npy"

if os.path.exists(FAISS_INDEX_PATH):
    print("Loading FAISS index from disk...")
    documents_index = faiss.read_index(FAISS_INDEX_PATH)
    docid_map = np.load(DOCID_MAP_PATH, allow_pickle=True).item()
else:
    print("Creating new FAISS index...")
    search_model = SentenceTransformer('all-MiniLM-L6-v2')
    documents_index = faiss.IndexFlatL2(384)
    docid_map = {}

def get_user_crud(db: Session = Depends(db.get_db)):
    return crud.UserCRUD(db)

def get_docs_crud(db: Session = Depends(db.get_db)):
    return crud.DocsCRUD(db)

def get_log_crud(db: Session = Depends(db.get_db)):
    return LogCRUD(db)

@app.get("/")
def root():
    return {"message": "Backend is running", "version": "1.0.0"}

# -----------------------------
# User Registration & Login
# -----------------------------
@app.post("/users/", response_model=schemas.User)
def create_user(user_in: schemas.UserCreate, user_crud: crud.UserCRUD = Depends(get_user_crud)):
    if user_crud.fetch_username(user_in.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    salt = encryption.gen_salt()
    hashed_pw = encryption.hash_password(user_in.password)
    user_uuid = encryption.gen_uuid(user_in.username, hashed_pw, salt)
    user = user_crud.create_user(
        uuid=user_uuid,
        username=user_in.username,
        hashed_password=hashed_pw,
        role=user_in.role,
        salt=salt
    )
    return user

@app.post("/token", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_crud: crud.UserCRUD = Depends(get_user_crud)
):
    user = user_crud.fetch_username(form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    stored_hash_bytes = user.hashed_password
    if not encryption.verify_password(form_data.password, stored_hash_bytes):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Add user info endpoint
@app.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

# -----------------------------
# Document Upload & Retrieval
# -----------------------------
@app.post("/documents/", response_model=schemas.Document)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(db.get_db),
    current_user: models.User = Depends(get_current_user),
    log_crud: LogCRUD = Depends(get_log_crud)
):
    
    allowed_file_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"]
    if file.content_type not in allowed_file_types:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a PDF, DOCX, or TXT file.")

    # 1. Save the file temporarily
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. Extract content, classify, and summarize
    try:
        document_content = utils.extract_text_from_file(file_path)
        category = classifier.classify_document(document_content)
        metadata = utils.extract_metadata(document_content)
        summary = utils.extractive_summarization(document_content)

    except Exception as e:
        # Clean up the temporary file if processing fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Error processing document: {str(e)}")

    finally:
        # Clean up the temporary unencrypted file
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # 3. Encrypt and save the document
    key = encryption.derive_key(current_user.hashed_password, current_user.salt)
    encrypted_data = encryption.encrypt_data(key, document_content)
    enc_path = f"{file_path}.enc"
    with open(enc_path, "wb") as f:
        f.write(encrypted_data)

    # 4. Save metadata to DB
    docs_crud = crud.DocsCRUD(db)
    new_doc = docs_crud.create_docs(
        uuid=current_user.uuid,
        filename=file.filename,
        filepath=enc_path,
        category=category,
        author=metadata["author"] or current_user.username,
        summary=summary
    )

    # 5. Index document for search
    try:
        embedding = search_model.encode(document_content)
        documents_index.add(np.expand_dims(embedding, axis=0))
        docid_map[documents_index.ntotal - 1] = new_doc.docid

        # Save index to disk
        faiss.write_index(documents_index, FAISS_INDEX_PATH)
        np.save(DOCID_MAP_PATH, docid_map)
    except Exception as e:
        print(f"Warning: Failed to index document: {str(e)}")

    log_crud.log_action(current_user.uuid, "upload", str(new_doc.docid))
    return new_doc


@app.get("/documents/", response_model=list[schemas.Document])
def list_documents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(db.get_db),
    current_user: models.User = Depends(get_current_user)
):
    docs_crud = crud.DocsCRUD(db)

    # Filter documents based on user role
    if current_user.role.lower() == "admin":
        # Admins can view all documents
        return docs_crud.fetch_all_docs(skip=skip, limit=limit)
    elif current_user.role.lower() in ["hr", "finance", "legal"]:
        # Specific roles can only see documents in their category
        return docs_crud.fetch_docs_by_role(current_user.role.title())
    else:
        # General users can only see documents they uploaded
        return docs_crud.fetch_docs_by_user_id(current_user.uuid)


@app.get("/documents/{docid}")
def get_document(
    docid: int,
    db: Session = Depends(db.get_db),
    current_user: models.User = Depends(get_current_user),
    log_crud: LogCRUD = Depends(get_log_crud)
):
    docs_crud = crud.DocsCRUD(db)
    doc = docs_crud.fetch_doc_by_doc_id(docid)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check permissions
    user_role = current_user.role.lower()
    if not (doc.uuid == current_user.uuid or 
            user_role == "admin" or 
            (user_role in ["hr", "finance", "legal"] and doc.category.lower() == user_role)):
        raise HTTPException(status_code=403, detail="Access denied")

    # Decrypt and return document details
    try:
        key = encryption.derive_key(current_user.hashed_password, current_user.salt)
        with open(doc.filepath, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = encryption.decrypt_data(key, encrypted_data)
        
        log_crud.log_action(current_user.uuid, "view", str(doc.docid))

        return {
            "docid": doc.docid,
            "filename": doc.filename,
            "author": doc.author,
            "category": doc.category,
            "summary": doc.summary,
            "upload_date": doc.upload_date,
            "content_preview": decrypted_data[:500] + "..." if len(decrypted_data) > 500 else decrypted_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accessing document: {str(e)}")


@app.get("/documents/{docid}/download")
def download_document(
    docid: int,
    db: Session = Depends(db.get_db),
    current_user: models.User = Depends(get_current_user),
    log_crud: LogCRUD = Depends(get_log_crud)
):
    docs_crud = crud.DocsCRUD(db)
    doc = docs_crud.fetch_doc_by_doc_id(docid)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check permissions
    user_role = current_user.role.lower()
    if not (doc.uuid == current_user.uuid or 
            user_role == "admin" or 
            (user_role in ["hr", "finance", "legal"] and doc.category.lower() == user_role)):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        key = encryption.derive_key(current_user.hashed_password, current_user.salt)
        with open(doc.filepath, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = encryption.decrypt_data(key, encrypted_data)
        
        log_crud.log_action(current_user.uuid, "download", str(doc.docid))
        
        # Create file stream
        file_stream = io.BytesIO(decrypted_data.encode('utf-8'))
        
        return StreamingResponse(
            io.BytesIO(decrypted_data.encode('utf-8')),
            media_type='application/octet-stream',
            headers={"Content-Disposition": f"attachment; filename={doc.filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading document: {str(e)}")


@app.get("/logs/", response_model=list[schemas.AccessLog])
def get_access_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(db.get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Check if the user has the HR or admin role
    if current_user.role.lower() not in ["hr", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view logs"
        )

    log_crud = crud.LogCRUD(db)
    return log_crud.fetch_all_logs(skip=skip, limit=limit)

# -----------------------------
# Indexing & Semantic Search
# -----------------------------
@app.get("/search/", response_model=list[schemas.Document])
def semantic_search(
    query: str, 
    limit: int = 10,
    db: Session = Depends(db.get_db),
    current_user: models.User = Depends(get_current_user),
    log_crud: LogCRUD = Depends(get_log_crud)
):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    docs_crud = crud.DocsCRUD(db)
    log_crud.log_action(current_user.uuid, "search")

    try:
        # 1. Get embedding for the query
        query_embedding = search_model.encode(query)
        query_embedding_np = np.expand_dims(query_embedding, axis=0)
        
        # 2. Search the FAISS index for similar documents
        if documents_index.ntotal == 0:
            return []
            
        k = min(limit, documents_index.ntotal)
        distances, indices = documents_index.search(query_embedding_np, k)
        
        # 3. Retrieve documents from the database based on search results
        results = []
        for i, index in enumerate(indices[0]):
            if index == -1:  # FAISS returns -1 for empty results
                continue
                
            # Check if index exists in the map
            if index in docid_map:
                doc_id = docid_map[index]
                doc = docs_crud.fetch_doc_by_doc_id(doc_id)
                
                # Apply role-based access control to the search results
                if doc:
                    user_role = current_user.role.lower()
                    if user_role == "admin" or \
                       (user_role in ["hr", "finance", "legal"] and doc.category.lower() == user_role) or \
                       doc.uuid == current_user.uuid:
                        # Add relevance score
                        doc_dict = schemas.Document.from_orm(doc).dict()
                        doc_dict["relevance_score"] = float(1.0 / (1.0 + distances[0][i]))  # Convert distance to similarity
                        results.append(doc_dict)

        # Sort by relevance score (highest first)
        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

# Health check endpoint
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "indexed_documents": documents_index.ntotal,
        "total_mappings": len(docid_map)
    }