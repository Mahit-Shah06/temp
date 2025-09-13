import PyPDF2
from docx import Document as DocxDocument
import re
import collections
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model 'en_core_web_sm'...")
    from spacy.cli import download
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def extract_text_from_file(file_path: str) -> str:
    """
    Extracts text content from a file based on its extension.
    Supports .txt, .pdf, and .docx files.
    """
    file_extension = file_path.split('.')[-1].lower()
    text = ""

    if file_extension == 'txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    elif file_extension == 'pdf':
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text()
    elif file_extension == 'docx':
        doc = DocxDocument(file_path)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
    
    return text.strip()

# New function for metadata extraction
def extract_metadata(text: str) -> dict:
    """
    Extracts title, author, date, and entities using regex and spaCy.
    """
    metadata = {
        "title": "Untitled Document",
        "author": None,
        "date": None,
        "entities": []
    }
    
    # 1. Extract Title: First line/sentence
    first_sentence_match = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text, 1)
    if first_sentence_match:
        metadata["title"] = first_sentence_match[0].strip()
    
    # 2. Extract Author: Look for "Author:", "By:", emails
    author_match = re.search(r'(?:Author:|By:)\s*([a-zA-Z\s]+(?:\s*<[\w\.-]+@[\w\.-]+>)?)\s*', text, re.IGNORECASE)
    if author_match:
        metadata["author"] = author_match.group(1).strip()
        
    # 3. Extract Date: Common date formats
    date_match = re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b', text, re.IGNORECASE)
    if date_match:
        metadata["date"] = date_match.group(0).strip()
        
    # 4. Extract Entities: Use spaCy
    doc = nlp(text)
    entities = [(ent.text, ent.label_) for ent in doc.ents if ent.label_ in ["PERSON", "ORG", "MONEY"]]
    metadata["entities"] = entities

    return metadata

# New function for summarization
def extractive_summarization(text: str, num_sentences: int = 3) -> str:
    """
    Generates an extractive summary using TF-IDF and cosine similarity.
    """
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)
    if len(sentences) <= num_sentences:
        return " ".join(sentences)
        
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(sentences)
    
    # Calculate similarity with the first sentence (as a proxy for key topic)
    sentence_scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix)
    
    # Rank and select top sentences
    ranked_sentences = np.argsort(sentence_scores[0])[::-1]
    top_indices = sorted(ranked_sentences[:num_sentences])
    
    summary = " ".join([sentences[i] for i in top_indices])
    return summary