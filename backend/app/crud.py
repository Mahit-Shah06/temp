from sqlalchemy.orm import Session
from . import models

class DocsCRUD():
    def __init__(self, db: Session):
        self.db = db

    def create_docs(self, uuid:str, filename: str, filepath: str, category: str, author: str = None, summary: str = None):
        doc = models.Document(
            uuid = uuid,
            filename=filename,
            filepath=filepath,
            category=category,
            author=author,
            summary=summary
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def fetch_all_docs(self, skip: int = 0, limit: int = 20):
        return self.db.query(models.Document).offset(skip).limit(limit).all()

    def fetch_doc_by_doc_id(self, doc_id: int):
        return self.db.query(models.Document).filter(models.Document.docid == doc_id).first()

    def fetch_docs_by_user_id(self, user_uuid: str):
        return self.db.query(models.Document).filter(models.Document.uuid == user_uuid).all()

    def fetch_docs_by_role(self, role: str):
        return self.db.query(models.Document).filter(models.Document.category == role).all()

    def delete_doc(self, doc_id: int):
        doc = self.fetch_doc_by_doc_id(doc_id)
        if doc:
            self.db.delete(doc)
            self.db.commit()
            return True
        return False

class UserCRUD:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, uuid: str, username: str, hashed_password: bytes, role: str, salt: bytes):
        user = models.User(
            uuid=uuid,
            username=username,
            hashed_password=hashed_password,
            role=role,
            salt=salt
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def fetch_username(self, username: str):
        return self.db.query(models.User).filter(models.User.username == username).first()
    
class LogCRUD:
    def __init__(self, db: Session):
        self.db = db
    
    def log_action(self, user_uuid: str, action: str, doc_uuid: str = None):
        log_entry = models.AccessLog(
            user_uuid=user_uuid,
            action=action,
            doc_uuid=doc_uuid
        )
        self.db.add(log_entry)
        self.db.commit()
        return log_entry
    
    def fetch_all_logs(self, skip: int = 0, limit: int = 100):
        return self.db.query(models.AccessLog).offset(skip).limit(limit).all()