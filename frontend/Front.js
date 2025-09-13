// Backend API Configuration
const API_BASE_URL = 'http://localhost:8000';

let currentUser = null;
let documents = [];
let accessToken = localStorage.getItem('access_token');

// API Helper Functions
async function apiCall(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const defaultHeaders = {
        'Content-Type': 'application/json',
    };

    if (accessToken) {
        defaultHeaders['Authorization'] = `Bearer ${accessToken}`;
    }

    const config = {
        ...options,
        headers: {
            ...defaultHeaders,
            ...options.headers
        }
    };

    try {
        const response = await fetch(url, config);
        
        if (!response.ok) {
            if (response.status === 401) {
                // Token expired, logout user
                logout();
                throw new Error('Session expired. Please login again.');
            }
            const errorData = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        
        return response;
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Auth Functions
function showLogin() {
    document.getElementById('loginPage').style.display = 'flex';
    document.getElementById('signupPage').style.display = 'none';
    document.getElementById('dashboard').style.display = 'none';
}

function showSignup() {
    document.getElementById('loginPage').style.display = 'none';
    document.getElementById('signupPage').style.display = 'flex';
    document.getElementById('dashboard').style.display = 'none';
}

function showDashboard() {
    document.getElementById('loginPage').style.display = 'none';
    document.getElementById('signupPage').style.display = 'none';
    document.getElementById('dashboard').style.display = 'block';
    loadDocuments();
    loadUserInfo();
}

function logout() {
    currentUser = null;
    accessToken = null;
    localStorage.removeItem('access_token');
    documents = [];
    showLogin();
}

// Login Form Handler
document.getElementById('loginForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;

    if (!username || !password) {
        alert('Please enter username and password');
        return;
    }

    try {
        // Show loading state
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Logging in...';
        submitBtn.disabled = true;

        // Create form data for OAuth2 login
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch(`${API_BASE_URL}/token`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            accessToken = data.access_token;
            localStorage.setItem('access_token', accessToken);
            
            // Get user info
            await loadUserInfo();
            showDashboard();
        } else {
            const errorData = await response.json();
            alert(errorData.detail || 'Login failed');
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Login failed. Please check your connection and try again.');
    } finally {
        // Reset button state
        const submitBtn = this.querySelector('button[type="submit"]');
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    }
});

// Signup Form Handler
document.getElementById('signupForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    
    const username = document.getElementById('signupUsername').value;
    const email = document.getElementById('signupEmail').value;
    const role = document.getElementById('signupRole').value;
    const password = document.getElementById('signupPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;

    if (password !== confirmPassword) {
        alert('Passwords do not match');
        return;
    }

    if (!username || !email || !role || !password) {
        alert('Please fill in all fields');
        return;
    }

    try {
        // Show loading state
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Creating Account...';
        submitBtn.disabled = true;

        const response = await apiCall('/users/', {
            method: 'POST',
            body: JSON.stringify({
                username: username,
                password: password,
                role: role
            })
        });

        if (response.ok) {
            alert('Account created successfully! Please login.');
            showLogin();
            // Clear form
            this.reset();
        }
    } catch (error) {
        console.error('Signup error:', error);
        alert(error.message || 'Registration failed. Please try again.');
    } finally {
        // Reset button state
        const submitBtn = this.querySelector('button[type="submit"]');
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    }
});

// Load user information
async function loadUserInfo() {
    try {
        const response = await apiCall('/users/me');
        const userData = await response.json();
        
        currentUser = userData;
        document.getElementById('userName').textContent = userData.username;
        document.getElementById('userAvatar').textContent = userData.username.charAt(0).toUpperCase();
    } catch (error) {
        console.error('Failed to load user info:', error);
    }
}

// Load documents from backend
async function loadDocuments() {
    try {
        const response = await apiCall('/documents/');
        documents = await response.json();
        renderDocuments(documents);
        updateFilters();
    } catch (error) {
        console.error('Failed to load documents:', error);
        alert('Failed to load documents. Please refresh the page.');
    }
}

// Render documents in the UI
function renderDocuments(docs) {
    const grid = document.getElementById('documentsGrid');
    
    if (docs.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #666;">
                <h3>No documents found</h3>
                <p>Upload some documents to get started!</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = docs.map(doc => `
        <div class="document-card" onclick="showDocumentDetail('${doc.docid}')">
            <span class="document-type type-${doc.category.toLowerCase()}">${doc.category}</span>
            <div class="document-title">${doc.filename}</div>
            <div class="document-meta">By: ${doc.author || 'Unknown'} • ${formatDate(doc.upload_date)}</div>
            <div class="document-summary">
                ${doc.summary || 'No summary available'}
            </div>
            <div class="document-actions">
                <button class="action-btn view-btn" onclick="event.stopPropagation(); showDocumentDetail('${doc.docid}')">👁️ View</button>
                <button class="action-btn download-btn" onclick="event.stopPropagation(); downloadDocument('${doc.docid}')">⬇️ Download</button>
            </div>
        </div>
    `).join('');
}

// Format date helper
function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Update filter dropdowns
function updateFilters() {
    // Update category filter
    const categories = [...new Set(documents.map(doc => doc.category))];
    const categoryFilter = document.getElementById('categoryFilter');
    categoryFilter.innerHTML = '<option value="">All Categories</option>' +
        categories.map(cat => `<option value="${cat.toLowerCase()}">${cat}</option>`).join('');

    // Update author filter
    const authors = [...new Set(documents.map(doc => doc.author).filter(Boolean))];
    const authorFilter = document.getElementById('authorFilter');
    authorFilter.innerHTML = '<option value="">All Authors</option>' +
        authors.map(author => `<option value="${author}">${author}</option>`).join('');
}

// File Upload Handler
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const progressBar = document.getElementById('progressBar');
const progressFill = document.getElementById('progressFill');

// Drag and Drop
uploadArea.addEventListener('dragover', function (e) {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', function (e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', function (e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    handleFileUpload(files);
});

fileInput.addEventListener('change', function (e) {
    const files = e.target.files;
    handleFileUpload(files);
});

async function handleFileUpload(files) {
    if (files.length === 0) return;

    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'];
    
    for (let file of files) {
        if (!allowedTypes.includes(file.type)) {
            alert(`File "${file.name}" is not supported. Please upload PDF, DOCX, or TXT files only.`);
            continue;
        }

        try {
            await uploadSingleFile(file);
        } catch (error) {
            console.error(`Failed to upload ${file.name}:`, error);
            alert(`Failed to upload ${file.name}: ${error.message}`);
        }
    }
    
    // Refresh documents list
    loadDocuments();
    
    // Clear file input
    fileInput.value = '';
}

async function uploadSingleFile(file) {
    progressBar.style.display = 'block';
    progressFill.style.width = '0%';

    const formData = new FormData();
    formData.append('file', file);

    try {
        // Simulate progress
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress = Math.min(progress + Math.random() * 30, 90);
            progressFill.style.width = progress + '%';
        }, 200);

        const response = await fetch(`${API_BASE_URL}/documents/`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${accessToken}`
            },
            body: formData
        });

        clearInterval(progressInterval);
        progressFill.style.width = '100%';

        if (response.ok) {
            const result = await response.json();
            console.log('Upload successful:', result);
            
            setTimeout(() => {
                progressBar.style.display = 'none';
                progressFill.style.width = '0%';
            }, 1000);
        } else {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Upload failed');
        }
    } catch (error) {
        progressBar.style.display = 'none';
        progressFill.style.width = '0%';
        throw error;
    }
}

// Search and Filter Functions
let searchTimeout;
document.getElementById('searchInput').addEventListener('input', function (e) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        const searchTerm = e.target.value.trim();
        if (searchTerm.length >= 3) {
            performSemanticSearch(searchTerm);
        } else if (searchTerm.length === 0) {
            renderDocuments(documents);
        }
    }, 500);
});

async function performSemanticSearch(query) {
    try {
        const response = await apiCall(`/search/?query=${encodeURIComponent(query)}`);
        const searchResults = await response.json();
        renderDocuments(searchResults);
    } catch (error) {
        console.error('Search failed:', error);
        alert('Search failed. Please try again.');
    }
}

document.getElementById('categoryFilter').addEventListener('change', filterDocuments);
document.getElementById('authorFilter').addEventListener('change', filterDocuments);
document.getElementById('dateFilter').addEventListener('change', filterDocuments);

function filterDocuments() {
    const categoryFilter = document.getElementById('categoryFilter').value.toLowerCase();
    const authorFilter = document.getElementById('authorFilter').value;
    const dateFilter = document.getElementById('dateFilter').value;

    let filteredDocs = documents;

    if (categoryFilter) {
        filteredDocs = filteredDocs.filter(doc => doc.category.toLowerCase() === categoryFilter);
    }

    if (authorFilter) {
        filteredDocs = filteredDocs.filter(doc => doc.author && doc.author.includes(authorFilter));
    }

    if (dateFilter) {
        const now = new Date();
        filteredDocs = filteredDocs.filter(doc => {
            const docDate = new Date(doc.upload_date);
            switch (dateFilter) {
                case 'today':
                    return docDate.toDateString() === now.toDateString();
                case 'week':
                    const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                    return docDate >= weekAgo;
                case 'month':
                    const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                    return docDate >= monthAgo;
                default:
                    return true;
            }
        });
    }

    renderDocuments(filteredDocs);
}

// Document Detail Modal
async function showDocumentDetail(docId) {
    try {
        const response = await apiCall(`/documents/${docId}`);
        const doc = await response.json();

        const modal = document.getElementById('documentModal');
        const details = document.getElementById('documentDetails');

        details.innerHTML = `
            <h2>${doc.filename}</h2>
            <div style="margin: 20px 0; padding: 20px; background: #f8fafc; border-radius: 12px;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 15px;">
                    <div><strong>Author:</strong> ${doc.author || 'Unknown'}</div>
                    <div><strong>Date:</strong> ${formatDate(doc.upload_date)}</div>
                    <div><strong>Category:</strong> ${doc.category}</div>
                    <div><strong>Document ID:</strong> ${doc.docid}</div>
                </div>
            </div>
            <h3>Summary</h3>
            <p style="margin: 15px 0; line-height: 1.6;">${doc.summary || 'No summary available'}</p>
            <h3>Content Preview</h3>
            <p style="margin: 15px 0; padding: 20px; background: #f8fafc; border-radius: 12px; line-height: 1.6; white-space: pre-wrap;">${doc.content_preview || 'No preview available'}</p>
            <div style="margin-top: 20px; display: flex; gap: 10px;">
                <button class="btn" style="width: auto; padding: 10px 20px;" onclick="downloadDocument('${doc.docid}')">Download Original</button>
                <button class="btn" style="width: auto; padding: 10px 20px; background: #38a169;" onclick="closeDocumentModal()">Close</button>
            </div>
        `;

        modal.style.display = 'block';
    } catch (error) {
        console.error('Failed to load document details:', error);
        alert('Failed to load document details. Please try again.');
    }
}

async function downloadDocument(docId) {
    try {
        const response = await fetch(`${API_BASE_URL}/documents/${docId}/download`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `document_${docId}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Download failed');
        }
    } catch (error) {
        console.error('Download failed:', error);
        alert('Download failed. Please try again.');
    }
}

function closeDocumentModal() {
    document.getElementById('documentModal').style.display = 'none';
}

// Close modal when clicking outside
document.getElementById('documentModal').addEventListener('click', function (e) {
    if (e.target === this) {
        closeDocumentModal();
    }
});

// Initialize application
document.addEventListener('DOMContentLoaded', function () {
    // Check if user is already logged in
    if (accessToken) {
        showDashboard();
    } else {
        showLogin();
    }
});

// Health check function (optional)
async function checkBackendHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            const health = await response.json();
            console.log('Backend health:', health);
        }
    } catch (error) {
        console.error('Backend health check failed:', error);
    }
}

// Run health check on page load
checkBackendHealth();