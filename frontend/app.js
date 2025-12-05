const API_BASE_URL = "https://invoice-qc-service-vishal-k-r.onrender.com";

let currentInvoiceData = null;
let currentPdfFile = null; // Store uploaded PDF file for preview
let currentFileType = null; // Store file type (pdf, image, docx)
let pdfDoc = null; // PDF.js document object
let currentPage = 1;
let totalPages = 1;
let currentZoom = 1.0; // Current zoom level
let renderTask = null; // Current PDF render task
let batchResultsData = null; // Store batch processing results
let isViewingFromBatch = false; // Track if viewing result from batch processing

// Test backend connection on load
async function testBackendConnection() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
        });
        if (response.ok) {
            const data = await response.json();
            console.log('Backend connection successful:', data);
            return true;
        } else {
            console.warn('Backend health check returned:', response.status);
            return false;
        }
    } catch (error) {
        console.error('Backend connection failed:', error);
        console.error('Make sure the backend is running on', API_BASE_URL);
        return false;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    try {
        // Test backend connection first
        testBackendConnection().then(isConnected => {
            if (!isConnected) {
                console.warn('Backend not connected. Some features may not work.');
            }
        });
        
        initializeNavigation();
        initializeUpload();
        initializeTabs();
        initializePreviewControls();
        initializeBackToBatch();
        initializeThemeToggle();
        loadDashboardStats();
        loadInvoices();

        const getStartedBtn = document.getElementById('get-started-btn');
        if (getStartedBtn) {
            getStartedBtn.addEventListener('click', () => {
                navigateToPage('upload');
            });
        }

        const uploadNewBtn = document.getElementById('upload-new-btn');
        if (uploadNewBtn) {
            uploadNewBtn.addEventListener('click', () => {
                navigateToPage('upload');
            });
        }

        const startOverBtn = document.getElementById('start-over-btn');
        if (startOverBtn) {
            startOverBtn.addEventListener('click', () => {
                navigateToPage('upload');
                currentInvoiceData = null;
            });
        }

        const saveAllBtn = document.getElementById('save-all-btn');
        if (saveAllBtn) {
            saveAllBtn.addEventListener('click', () => {
                alert('Invoice has been saved successfully!');
                navigateToPage('invoices');
                loadInvoices();
            });
        }

        const downloadCsvBtn = document.getElementById('download-csv-btn');
        if (downloadCsvBtn) {
            downloadCsvBtn.addEventListener('click', downloadCSV);
        }

        const downloadJsonBtn = document.getElementById('download-json-btn');
        if (downloadJsonBtn) {
            downloadJsonBtn.addEventListener('click', downloadJSON);
        }
    } catch (error) {
        console.error('Error initializing application:', error);
    }
});

function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.getAttribute('data-page');
            navigateToPage(page);
        });
    });
}

function navigateToPage(page) {
    try {
        // Remove active class from all nav items
        document.querySelectorAll('.nav-item').forEach(item => {
            if (item && item.classList) {
                item.classList.remove('active');
            }
        });
        
        // Add active class to selected nav item
        const navItem = document.querySelector(`[data-page="${page}"]`);
        if (navItem && navItem.classList) {
            navItem.classList.add('active');
        }

        // Remove active class from all page contents
        document.querySelectorAll('.page-content').forEach(content => {
            if (content && content.classList) {
                content.classList.remove('active');
            }
        });
        
        // Add active class to selected page
        const pageElement = document.getElementById(`${page}-page`);
        if (pageElement && pageElement.classList) {
            pageElement.classList.add('active');
        }

        // Update page title
        const pageTitles = {
            'dashboard': 'Dashboard',
            'upload': 'Upload & Process',
            'results': 'Extraction Results',
            'invoices': 'All Invoices',
            'documentation': 'Documentation'
        };
        const pageTitleElement = document.querySelector('.page-title');
        if (pageTitleElement) {
            pageTitleElement.textContent = pageTitles[page] || 'Page';
        }

        if (page === 'invoices') {
            loadInvoices();
        }
        
        // When navigating to upload page, restore batch results if available
        if (page === 'upload' && batchResultsData) {
            // Small delay to ensure page is rendered
            setTimeout(() => {
                displayBatchResults(batchResultsData.result, batchResultsData.files);
            }, 100);
        }
    } catch (error) {
        console.error('Error navigating to page:', page, error);
    }
}

function initializeBackToBatch() {
    const backToBatchBtn = document.getElementById('back-to-batch-btn');
    if (backToBatchBtn) {
        backToBatchBtn.addEventListener('click', () => {
            // Navigate back to upload page and show batch results
            navigateToPage('upload');
            // Scroll to batch results after navigation
            setTimeout(() => {
                const batchResultsContainer = document.getElementById('batch-results-container');
                if (batchResultsContainer) {
                    batchResultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 200);
        });
    }
}

function initializeThemeToggle() {
    // Get saved theme preference or default to light
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);
    
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            applyTheme(newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }
}

function applyTheme(theme) {
    if (theme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        // Update icon visibility
        const sunIcon = document.getElementById('theme-icon-sun');
        const moonIcon = document.getElementById('theme-icon-moon');
        if (sunIcon) sunIcon.style.display = 'block';
        if (moonIcon) moonIcon.style.display = 'none';
    } else {
        document.documentElement.setAttribute('data-theme', 'light');
        // Update icon visibility
        const sunIcon = document.getElementById('theme-icon-sun');
        const moonIcon = document.getElementById('theme-icon-moon');
        if (sunIcon) sunIcon.style.display = 'none';
        if (moonIcon) moonIcon.style.display = 'block';
    }
}

function initializeUpload() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const uploadBtn = document.getElementById('upload-btn');

    if (!uploadArea || !fileInput || !uploadBtn) {
        console.error('Upload elements not found');
        return;
    }

    uploadBtn.addEventListener('click', () => {
        fileInput.click();
    });

    uploadArea.addEventListener('click', (e) => {
        if (e.target === uploadArea || e.target.closest('.upload-area')) {
            fileInput.click();
        }
    });

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'var(--primary-color)';
        uploadArea.style.background = 'rgba(91, 95, 237, 0.05)';
    });

    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '';
        uploadArea.style.background = '';
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '';
        uploadArea.style.background = '';

        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            if (files.length === 1) {
                handleFileUpload(files[0]);
            } else {
                handleBatchUpload(files);
            }
        }
    });

    fileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            if (files.length === 1) {
                handleFileUpload(files[0]);
            } else {
                handleBatchUpload(files);
            }
        }
    });
}

async function handleFileUpload(file) {
    const fileName = file.name.toLowerCase();
    
    if (!fileName.endsWith('.pdf')) {
        alert('Only PDF files are supported.');
        return;
    }

    if (file.size > 35 * 1024 * 1024) {
        alert('File size exceeds 35MB limit');
        return;
    }

    const processingIndicator = document.getElementById('processing-indicator');
    if (processingIndicator) {
        processingIndicator.style.display = 'block';
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            // Try to get error message from response
            let errorMessage = 'Upload failed';
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorData.message || errorMessage;
            } catch (e) {
                errorMessage = `Server error: ${response.status} ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }

        const result = await response.json();
        
        if (!result || !result.validation_result) {
            throw new Error('Invalid response from server');
        }
        
        currentInvoiceData = result;
        currentPdfFile = file; // Store file for preview

        if (processingIndicator) {
            processingIndicator.style.display = 'none';
        }

        try {
            displayResults(result, file.name);
            navigateToPage('results');
        } catch (displayError) {
            console.error('Error displaying results:', displayError);
            alert('Error displaying results. Please check the console for details.');
            if (processingIndicator) {
                processingIndicator.style.display = 'none';
            }
        }

    } catch (error) {
        console.error('Error uploading file:', error);
        
        // Show detailed error message
        let errorMessage = 'Error processing invoice. ';
        
        if (error.name === 'TypeError' && error.message && error.message.includes('fetch')) {
            errorMessage += 'Cannot connect to backend server. Please ensure:\n';
            errorMessage += '1. Backend is running on http://localhost:8000\n';
            errorMessage += '2. Check browser console for CORS errors\n';
            errorMessage += '3. Verify backend health at http://localhost:8000/health';
        } else if (error.message) {
            errorMessage += error.message;
        } else {
            errorMessage += 'Unknown error occurred. Please check the browser console for details.';
        }
        
        alert(errorMessage);
        if (processingIndicator) {
            processingIndicator.style.display = 'none';
        }
    }
}

async function handleBatchUpload(files) {
    // Validate files
    const validFiles = [];
    const invalidFiles = [];
    
    for (const file of files) {
        const fileName = file.name.toLowerCase();
        
        if (!fileName.endsWith('.pdf')) {
            invalidFiles.push(file.name);
            continue;
        }
        if (file.size > 35 * 1024 * 1024) {
            invalidFiles.push(`${file.name} (exceeds 35MB)`);
            continue;
        }
        validFiles.push(file);
    }
    
    if (invalidFiles.length > 0) {
        alert(`Invalid files:\n${invalidFiles.join('\n')}\n\nOnly PDF files under 35MB are supported.`);
    }
    
    if (validFiles.length === 0) {
        return;
    }
    
    if (validFiles.length > 50) {
        alert('Maximum 50 files allowed per batch. Please select fewer files.');
        return;
    }
    
    // Show processing indicator
    const processingIndicator = document.getElementById('processing-indicator');
    const processingMessage = document.getElementById('processing-message');
    const batchProgress = document.getElementById('batch-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    if (processingIndicator) {
        processingIndicator.style.display = 'block';
    }
    if (processingMessage) {
        processingMessage.textContent = `Processing ${validFiles.length} file(s)...`;
    }
    if (batchProgress) {
        batchProgress.style.display = 'block';
    }
    if (progressFill) {
        progressFill.style.width = '0%';
    }
        if (progressText) {
            progressText.textContent = `0 / ${validFiles.length} files processed`;
        }
    
    // Hide batch results container
    const batchResultsContainer = document.getElementById('batch-results-container');
    if (batchResultsContainer) {
        batchResultsContainer.style.display = 'none';
    }
    
    try {
        // Prepare FormData with all files
        const formData = new FormData();
        validFiles.forEach(file => {
            formData.append('files', file);
        });
        
        // Upload files
        const response = await fetch(`${API_BASE_URL}/api/upload/batch`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            let errorMessage = 'Batch upload failed';
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorData.message || errorMessage;
            } catch (e) {
                errorMessage = `Server error: ${response.status} ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }
        
        const result = await response.json();
        
        // Update progress to 100%
        if (progressFill) {
            progressFill.style.width = '100%';
        }
        if (progressText) {
            progressText.textContent = `${result.successful} / ${result.total_files} files processed successfully`;
        }
        
        // Display batch results
        displayBatchResults(result, validFiles);
        
        // Hide processing indicator after a short delay
        setTimeout(() => {
            if (processingIndicator) {
                processingIndicator.style.display = 'none';
            }
        }, 1000);
        
        // Reload dashboard stats
        loadDashboardStats();
        
    } catch (error) {
        console.error('Error in batch upload:', error);
        
        if (processingIndicator) {
            processingIndicator.style.display = 'none';
        }
        
        alert(`Batch upload error: ${error.message || 'Unknown error occurred'}`);
    }
}

function displayBatchResults(result, files) {
    const batchResultsContainer = document.getElementById('batch-results-container');
    const batchResultsSummary = document.getElementById('batch-results-summary');
    const batchResultsList = document.getElementById('batch-results-list');
    
    if (!batchResultsContainer || !batchResultsSummary || !batchResultsList) {
        console.error('Batch results elements not found');
        return;
    }
    
    // Store batch results in state for navigation
    batchResultsData = {
        result: result,
        files: files,
        timestamp: Date.now()
    };
    isViewingFromBatch = false; // We're viewing batch results, not individual result
    
    // Show container
    batchResultsContainer.style.display = 'block';
    
    // Create summary
    const successRate = result.total_files > 0 
        ? ((result.successful / result.total_files) * 100).toFixed(1) 
        : 0;
    
    batchResultsSummary.innerHTML = `
        <div class="batch-summary-stats">
            <div class="summary-stat">
                <span class="stat-label">Total Files</span>
                <span class="stat-value">${result.total_files}</span>
            </div>
            <div class="summary-stat success">
                <span class="stat-label">Successful</span>
                <span class="stat-value">${result.successful}</span>
            </div>
            <div class="summary-stat ${result.failed > 0 ? 'error' : ''}">
                <span class="stat-label">Failed</span>
                <span class="stat-value">${result.failed}</span>
            </div>
            <div class="summary-stat">
                <span class="stat-label">Success Rate</span>
                <span class="stat-value">${successRate}%</span>
            </div>
        </div>
    `;
    
    // Create results list
    batchResultsList.innerHTML = '';
    
    // Show successful results
    if (result.results && result.results.length > 0) {
        const successSection = document.createElement('div');
        successSection.className = 'batch-results-section';
        successSection.innerHTML = '<h4 class="results-section-title">✓ Successfully Processed</h4>';
        
        const successList = document.createElement('div');
        successList.className = 'results-items';
        
        result.results.forEach((item, index) => {
            const resultItem = document.createElement('div');
            resultItem.className = 'result-item success';
            const validationResult = item.validation_result || {};
            const score = validationResult.score || 0;
            const scoreClass = score >= 80 ? 'high' : score >= 60 ? 'medium' : 'low';
            
            resultItem.innerHTML = `
                <div class="result-item-header">
                    <span class="result-filename">${item.filename || 'Unknown'}</span>
                    <span class="result-score score-${scoreClass}">Score: ${score}</span>
                </div>
                <div class="result-item-details">
                    <span>Invoice: ${validationResult.invoice_number || 'N/A'}</span>
                    <span>Vendor: ${validationResult.extracted_data?.vendor_name || 'N/A'}</span>
                    <span>Amount: ${validationResult.extracted_data?.total_amount || 'N/A'}</span>
                </div>
            `;
            
            // Add click handler to view details
            resultItem.addEventListener('click', async () => {
                if (item.validation_result) {
                    // Mark that we're viewing from batch results
                    isViewingFromBatch = true;
                    
                    currentInvoiceData = {
                        success: true,
                        invoice_id: item.invoice_id,
                        validation_result: item.validation_result,
                        message: 'Invoice processed successfully'
                    };
                    
                    // Try to fetch stored file if invoice_id exists
                    let showPreview = false;
                    if (item.invoice_id) {
                        try {
                            const fileResponse = await fetch(`${API_BASE_URL}/api/invoices/${item.invoice_id}/file`);
                            if (fileResponse.ok) {
                                const blob = await fileResponse.blob();
                                const file = new File([blob], item.filename || 'file', { type: blob.type });
                                currentPdfFile = file;
                                showPreview = true;
                            }
                        } catch (fileError) {
                            console.warn('Could not load file for preview:', fileError);
                        }
                    }
                    
                    // Mark that we're viewing from batch results
                    isViewingFromBatch = true;
                    
                    displayResults(currentInvoiceData, item.filename || 'file', showPreview);
                    navigateToPage('results');
                }
            });
            
            successList.appendChild(resultItem);
        });
        
        successSection.appendChild(successList);
        batchResultsList.appendChild(successSection);
    }
    
    // Show errors
    if (result.errors && result.errors.length > 0) {
        const errorSection = document.createElement('div');
        errorSection.className = 'batch-results-section';
        errorSection.innerHTML = '<h4 class="results-section-title error">✗ Failed to Process</h4>';
        
        const errorList = document.createElement('div');
        errorList.className = 'results-items';
        
        result.errors.forEach(error => {
            const errorItem = document.createElement('div');
            errorItem.className = 'result-item error';
            errorItem.innerHTML = `
                <div class="result-item-header">
                    <span class="result-filename">${error.filename || 'Unknown'}</span>
                </div>
                <div class="result-item-details">
                    <span class="error-message">${error.error || 'Unknown error'}</span>
                </div>
            `;
            errorList.appendChild(errorItem);
        });
        
        errorSection.appendChild(errorList);
        batchResultsList.appendChild(errorSection);
    }
    
    // Scroll to results
    batchResultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function displayResults(data, filename, showPreview = true) {
    if (!data || !data.validation_result) {
        console.error('Invalid data structure:', data);
        alert('Error: Invalid response data');
        return;
    }

    // Show/hide back button based on whether viewing from batch
    const backToBatchBtn = document.getElementById('back-to-batch-btn');
    if (backToBatchBtn) {
        if (isViewingFromBatch && batchResultsData) {
            backToBatchBtn.style.display = 'flex';
        } else {
            backToBatchBtn.style.display = 'none';
        }
    }

    const pdfNameElement = document.getElementById('pdf-name');
    if (pdfNameElement) {
        pdfNameElement.textContent = filename;
    }

    // Display file preview if available
    if (showPreview && currentPdfFile) {
        displayPdfPreview(currentPdfFile);
    } else {
        // Hide preview if no file available
        const pdfPreview = document.getElementById('pdf-preview');
        const pdfCanvas = document.getElementById('pdf-canvas');
        const imagePreview = document.getElementById('image-preview');
        const docxPreview = document.getElementById('docx-preview');
        const pdfPlaceholder = document.getElementById('pdf-preview-placeholder');
        const previewNavigation = document.getElementById('preview-navigation');
        
        if (pdfPreview) pdfPreview.style.display = 'none';
        if (pdfCanvas) pdfCanvas.style.display = 'none';
        if (imagePreview) imagePreview.style.display = 'none';
        if (docxPreview) docxPreview.style.display = 'none';
        if (previewNavigation) previewNavigation.style.display = 'none';
        if (pdfPlaceholder) pdfPlaceholder.style.display = 'flex';
    }

    const validationResult = data.validation_result;
    const extractedData = validationResult?.extracted_data;

    if (!extractedData) {
        console.error('No extracted data found:', validationResult);
        alert('Error: No extracted data found in response');
        return;
    }

    const statusBadge = document.getElementById('status-badge');
    if (statusBadge) {
        statusBadge.textContent = `Score: ${validationResult.score || 0}`;

        if (validationResult.score >= 80) {
            statusBadge.style.background = '#28A745';
        } else if (validationResult.score >= 60) {
            statusBadge.style.background = '#FFC107';
        } else {
            statusBadge.style.background = '#DC3545';
        }
    }

    const dataGrid = document.getElementById('data-grid');
    if (!dataGrid) {
        console.error('Data grid element not found');
        return;
    }
    dataGrid.innerHTML = '';

    const fields = [
        { key: 'invoice_number', label: 'Invoice Number' },
        { key: 'vendor_name', label: 'Vendor Name' },
        { key: 'buyer_name', label: 'Buyer Name' },
        { key: 'invoice_date', label: 'Invoice Date' },
        { key: 'due_date', label: 'Due Date' },
        { key: 'currency', label: 'Currency' },
        { key: 'total_amount', label: 'Total Amount' },
        { key: 'subtotal', label: 'Subtotal' },
        { key: 'tax_amount', label: 'Tax Amount' },
        { key: 'payment_terms', label: 'Payment Terms' }
    ];

    fields.forEach(field => {
        const value = extractedData[field.key];
        const fieldElement = document.createElement('div');
        fieldElement.className = 'data-field';
        fieldElement.innerHTML = `
            <div class="field-label">${field.label}</div>
            <div class="field-value ${!value ? 'missing' : ''}">${value || 'Not found'}</div>
        `;
        dataGrid.appendChild(fieldElement);
    });

    if (extractedData.line_items && extractedData.line_items.length > 0) {
        const lineItemsSection = document.getElementById('line-items-section');
        if (lineItemsSection) {
            lineItemsSection.style.display = 'block';
        }
        const tbody = document.getElementById('line-items-tbody');
        if (tbody) {
            tbody.innerHTML = '';

            extractedData.line_items.forEach(item => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${item.description || '-'}</td>
                    <td>${item.quantity || '-'}</td>
                    <td>${item.price || '-'}</td>
                    <td>${item.total || '-'}</td>
                `;
                tbody.appendChild(row);
            });
        }
    } else {
        const lineItemsSection = document.getElementById('line-items-section');
        if (lineItemsSection) {
            lineItemsSection.style.display = 'none';
        }
    }

    const jsonContent = document.getElementById('json-content');
    if (jsonContent) {
        jsonContent.textContent = JSON.stringify(extractedData, null, 2);
    }
}

// Initialize PDF.js worker
if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}

function initializePreviewControls() {
    // Zoom controls
    const zoomInBtn = document.getElementById('zoom-in-btn');
    const zoomOutBtn = document.getElementById('zoom-out-btn');
    const fitWidthBtn = document.getElementById('fit-width-btn');
    const fitPageBtn = document.getElementById('fit-page-btn');
    
    if (zoomInBtn) {
        zoomInBtn.addEventListener('click', () => adjustZoom(0.25));
    }
    if (zoomOutBtn) {
        zoomOutBtn.addEventListener('click', () => adjustZoom(-0.25));
    }
    if (fitWidthBtn) {
        fitWidthBtn.addEventListener('click', () => fitToWidth());
    }
    if (fitPageBtn) {
        fitPageBtn.addEventListener('click', () => fitToPage());
    }
    
    // Navigation controls
    const prevPageBtn = document.getElementById('prev-page-btn');
    const nextPageBtn = document.getElementById('next-page-btn');
    const pageInput = document.getElementById('page-input');
    
    if (prevPageBtn) {
        prevPageBtn.addEventListener('click', () => goToPage(currentPage - 1));
    }
    if (nextPageBtn) {
        nextPageBtn.addEventListener('click', () => goToPage(currentPage + 1));
    }
    if (pageInput) {
        pageInput.addEventListener('change', (e) => {
            const page = parseInt(e.target.value);
            if (page >= 1 && page <= totalPages) {
                goToPage(page);
            } else {
                e.target.value = currentPage;
            }
        });
    }
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        
        if (e.key === 'ArrowLeft' && e.ctrlKey) {
            e.preventDefault();
            goToPage(currentPage - 1);
        } else if (e.key === 'ArrowRight' && e.ctrlKey) {
            e.preventDefault();
            goToPage(currentPage + 1);
        } else if (e.key === '+' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            adjustZoom(0.25);
        } else if (e.key === '-' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            adjustZoom(-0.25);
        } else if (e.key === '0' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            fitToPage();
        }
    });
}

async function displayPdfPreview(file) {
    if (!file) {
        console.warn('No file available for preview');
        return;
    }

    const fileName = file.name.toLowerCase();
    currentPdfFile = file;
    
    // Determine file type
    if (fileName.endsWith('.pdf')) {
        currentFileType = 'pdf';
        await displayPDF(file);
    } else if (fileName.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/i)) {
        currentFileType = 'image';
        displayImage(file);
    } else if (fileName.endsWith('.docx')) {
        currentFileType = 'docx';
        await displayDOCX(file);
    } else {
        // Fallback to iframe for other file types
        currentFileType = 'other';
        displayGenericPreview(file);
    }
}

async function displayPDF(file) {
    const pdfCanvas = document.getElementById('pdf-canvas');
    const pdfPreview = document.getElementById('pdf-preview');
    const pdfPlaceholder = document.getElementById('pdf-preview-placeholder');
    const previewLoading = document.getElementById('preview-loading');
    const previewNavigation = document.getElementById('preview-navigation');
    
    if (!pdfCanvas || !pdfPlaceholder) {
        console.warn('PDF preview elements not found');
        return;
    }

    // Check if PDF.js is available
    if (typeof pdfjsLib === 'undefined') {
        console.warn('PDF.js library not loaded, falling back to iframe');
        displayGenericPreview(file);
        return;
    }

    try {
        // Show loading indicator
        pdfPlaceholder.style.display = 'none';
        pdfPreview.style.display = 'none';
        pdfCanvas.style.display = 'none';
        if (previewLoading) previewLoading.style.display = 'flex';
        
        // Cancel any ongoing render task
        if (renderTask) {
            renderTask.cancel();
        }
        
        // Load PDF using PDF.js
        const arrayBuffer = await file.arrayBuffer();
        pdfDoc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        totalPages = pdfDoc.numPages;
        currentPage = 1;
        currentZoom = 1.0;
        
        // Update UI
        updatePageInfo();
        if (previewNavigation) {
            previewNavigation.style.display = 'flex';
        }
        
        // Render first page
        await renderPDFPage(currentPage);
        
        // Hide loading, show canvas
        if (previewLoading) previewLoading.style.display = 'none';
        pdfCanvas.style.display = 'block';
        
    } catch (error) {
        console.error('Error displaying PDF preview:', error);
        if (previewLoading) previewLoading.style.display = 'none';
        // Fallback to iframe if PDF.js fails
        try {
            displayGenericPreview(file);
        } catch (fallbackError) {
            pdfPlaceholder.style.display = 'flex';
            pdfCanvas.style.display = 'none';
            if (previewNavigation) previewNavigation.style.display = 'none';
        }
    }
}

async function renderPDFPage(pageNum) {
    if (!pdfDoc || pageNum < 1 || pageNum > totalPages) return;
    
    const pdfCanvas = document.getElementById('pdf-canvas');
    const previewLoading = document.getElementById('preview-loading');
    
    if (!pdfCanvas) return;
    
    try {
        // Cancel any ongoing render task
        if (renderTask) {
            renderTask.cancel();
        }
        
        // Show loading for page changes
        if (pageNum !== currentPage && previewLoading) {
            previewLoading.style.display = 'flex';
        }
        
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: currentZoom });
        
        // Set canvas dimensions
        pdfCanvas.height = viewport.height;
        pdfCanvas.width = viewport.width;
        
        const context = pdfCanvas.getContext('2d');
        
        // Render page
        renderTask = page.render({
            canvasContext: context,
            viewport: viewport
        });
        
        await renderTask.promise;
        currentPage = pageNum;
        
        // Update UI
        updatePageInfo();
        if (previewLoading) previewLoading.style.display = 'none';
        pdfCanvas.style.display = 'block';
        
    } catch (error) {
        if (error.name !== 'RenderingCancelledException') {
            console.error('Error rendering PDF page:', error);
        }
        if (previewLoading) previewLoading.style.display = 'none';
    }
}

function displayImage(file) {
    const imagePreview = document.getElementById('image-preview');
    const pdfPlaceholder = document.getElementById('pdf-preview-placeholder');
    const previewLoading = document.getElementById('preview-loading');
    const previewNavigation = document.getElementById('preview-navigation');
    
    if (!imagePreview || !pdfPlaceholder) {
        console.warn('Image preview elements not found');
        return;
    }

    try {
        // Hide other previews
        pdfPlaceholder.style.display = 'none';
        document.getElementById('pdf-canvas').style.display = 'none';
        document.getElementById('pdf-preview').style.display = 'none';
        document.getElementById('docx-preview').style.display = 'none';
        if (previewNavigation) previewNavigation.style.display = 'none';
        
        // Show loading
        if (previewLoading) previewLoading.style.display = 'flex';
        
        const imageUrl = URL.createObjectURL(file);
        imagePreview.onload = () => {
            if (previewLoading) previewLoading.style.display = 'none';
            imagePreview.style.display = 'block';
            currentZoom = 1.0;
            updateZoomLevel();
            // Reset image styles on load
            imagePreview.style.width = '';
            imagePreview.style.height = '';
            imagePreview.style.maxWidth = '100%';
            imagePreview.style.maxHeight = '600px';
        };
        imagePreview.onerror = () => {
            if (previewLoading) previewLoading.style.display = 'none';
            pdfPlaceholder.style.display = 'flex';
        };
        imagePreview.src = imageUrl;
        
    } catch (error) {
        console.error('Error displaying image preview:', error);
        if (previewLoading) previewLoading.style.display = 'none';
        pdfPlaceholder.style.display = 'flex';
    }
}

async function displayDOCX(file) {
    const docxPreview = document.getElementById('docx-preview');
    const pdfPlaceholder = document.getElementById('pdf-preview-placeholder');
    const previewLoading = document.getElementById('preview-loading');
    const previewNavigation = document.getElementById('preview-navigation');
    
    if (!docxPreview || !pdfPlaceholder) {
        console.warn('DOCX preview elements not found');
        return;
    }

    try {
        // Hide other previews
        pdfPlaceholder.style.display = 'none';
        document.getElementById('pdf-canvas').style.display = 'none';
        document.getElementById('pdf-preview').style.display = 'none';
        document.getElementById('image-preview').style.display = 'none';
        if (previewNavigation) previewNavigation.style.display = 'none';
        
        // Show loading
        if (previewLoading) previewLoading.style.display = 'flex';
        
        if (typeof mammoth === 'undefined') {
            throw new Error('Mammoth.js library not loaded');
        }
        
        const arrayBuffer = await file.arrayBuffer();
        const result = await mammoth.convertToHtml({ arrayBuffer: arrayBuffer });
        
        docxPreview.innerHTML = result.value;
        
        if (previewLoading) previewLoading.style.display = 'none';
        docxPreview.style.display = 'block';
        
    } catch (error) {
        console.error('Error displaying DOCX preview:', error);
        if (previewLoading) previewLoading.style.display = 'none';
        pdfPlaceholder.style.display = 'flex';
    }
}

function displayGenericPreview(file) {
    const pdfPreview = document.getElementById('pdf-preview');
    const pdfPlaceholder = document.getElementById('pdf-preview-placeholder');
    const previewLoading = document.getElementById('preview-loading');
    const previewNavigation = document.getElementById('preview-navigation');
    
    if (!pdfPreview || !pdfPlaceholder) {
        console.warn('Preview elements not found');
        return;
    }

    try {
        // Hide other previews
        pdfPlaceholder.style.display = 'none';
        document.getElementById('pdf-canvas').style.display = 'none';
        document.getElementById('image-preview').style.display = 'none';
        document.getElementById('docx-preview').style.display = 'none';
        if (previewNavigation) previewNavigation.style.display = 'none';
        
        const fileUrl = URL.createObjectURL(file);
        pdfPreview.src = fileUrl;
        pdfPreview.style.display = 'block';
        
    } catch (error) {
        console.error('Error displaying generic preview:', error);
        pdfPlaceholder.style.display = 'flex';
        pdfPreview.style.display = 'none';
    }
}

function adjustZoom(delta) {
    if (currentFileType === 'pdf' && pdfDoc) {
        currentZoom = Math.max(0.5, Math.min(3.0, currentZoom + delta));
        updateZoomLevel();
        renderPDFPage(currentPage);
    } else if (currentFileType === 'image') {
        const imagePreview = document.getElementById('image-preview');
        if (imagePreview && imagePreview.complete) {
            currentZoom = Math.max(0.5, Math.min(3.0, currentZoom + delta));
            updateZoomLevel();
            const naturalWidth = imagePreview.naturalWidth;
            const naturalHeight = imagePreview.naturalHeight;
            imagePreview.style.width = `${naturalWidth * currentZoom}px`;
            imagePreview.style.height = `${naturalHeight * currentZoom}px`;
            imagePreview.style.maxWidth = 'none';
            imagePreview.style.maxHeight = 'none';
        }
    }
}

function fitToWidth() {
    if (currentFileType === 'pdf' && pdfDoc) {
        const wrapper = document.getElementById('preview-wrapper');
        if (wrapper && pdfDoc) {
            const wrapperWidth = wrapper.clientWidth - 40; // Account for padding
            pdfDoc.getPage(currentPage).then(page => {
                const viewport = page.getViewport({ scale: 1.0 });
                currentZoom = wrapperWidth / viewport.width;
                updateZoomLevel();
                renderPDFPage(currentPage);
            });
        }
    } else if (currentFileType === 'image') {
        const imagePreview = document.getElementById('image-preview');
        const wrapper = document.getElementById('preview-wrapper');
        if (imagePreview && wrapper && imagePreview.complete) {
            const wrapperWidth = wrapper.clientWidth - 40;
            currentZoom = wrapperWidth / imagePreview.naturalWidth;
            updateZoomLevel();
            imagePreview.style.width = `${imagePreview.naturalWidth * currentZoom}px`;
            imagePreview.style.height = `${imagePreview.naturalHeight * currentZoom}px`;
            imagePreview.style.maxWidth = 'none';
            imagePreview.style.maxHeight = 'none';
        }
    }
}

function fitToPage() {
    if (currentFileType === 'pdf' && pdfDoc) {
        const wrapper = document.getElementById('preview-wrapper');
        if (wrapper && pdfDoc) {
            const wrapperWidth = wrapper.clientWidth - 40;
            const wrapperHeight = wrapper.clientHeight - 40;
            pdfDoc.getPage(currentPage).then(page => {
                const viewport = page.getViewport({ scale: 1.0 });
                const scaleX = wrapperWidth / viewport.width;
                const scaleY = wrapperHeight / viewport.height;
                currentZoom = Math.min(scaleX, scaleY);
                updateZoomLevel();
                renderPDFPage(currentPage);
            });
        }
    } else if (currentFileType === 'image') {
        const imagePreview = document.getElementById('image-preview');
        const wrapper = document.getElementById('preview-wrapper');
        if (imagePreview && wrapper && imagePreview.complete) {
            const wrapperWidth = wrapper.clientWidth - 40;
            const wrapperHeight = wrapper.clientHeight - 40;
            const scaleX = wrapperWidth / imagePreview.naturalWidth;
            const scaleY = wrapperHeight / imagePreview.naturalHeight;
            currentZoom = Math.min(scaleX, scaleY);
            updateZoomLevel();
            imagePreview.style.width = `${imagePreview.naturalWidth * currentZoom}px`;
            imagePreview.style.height = `${imagePreview.naturalHeight * currentZoom}px`;
            imagePreview.style.maxWidth = '100%';
            imagePreview.style.maxHeight = '600px';
        }
    }
}

function goToPage(pageNum) {
    if (currentFileType === 'pdf' && pdfDoc) {
        if (pageNum >= 1 && pageNum <= totalPages) {
            renderPDFPage(pageNum);
            const pageInput = document.getElementById('page-input');
            if (pageInput) {
                pageInput.value = pageNum;
            }
        }
    }
}

function updatePageInfo() {
    const pageInfo = document.getElementById('pdf-page-info');
    const totalPagesEl = document.getElementById('total-pages');
    const pageInput = document.getElementById('page-input');
    const prevBtn = document.getElementById('prev-page-btn');
    const nextBtn = document.getElementById('next-page-btn');
    
    if (currentFileType === 'pdf') {
        if (pageInfo) {
            pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
        }
        if (totalPagesEl) {
            totalPagesEl.textContent = totalPages;
        }
        if (pageInput) {
            pageInput.value = currentPage;
            pageInput.max = totalPages;
        }
        if (prevBtn) {
            prevBtn.disabled = currentPage <= 1;
        }
        if (nextBtn) {
            nextBtn.disabled = currentPage >= totalPages;
        }
    } else {
        if (pageInfo) {
            pageInfo.textContent = '';
        }
    }
}

function updateZoomLevel() {
    const zoomLevel = document.getElementById('zoom-level');
    if (zoomLevel) {
        zoomLevel.textContent = `${Math.round(currentZoom * 100)}%`;
    }
}

function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    if (tabButtons.length === 0) {
        // Tabs might not exist on all pages, that's okay
        return;
    }
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            tabButtons.forEach(btn => {
                if (btn && btn.classList) {
                    btn.classList.remove('active');
                }
            });
            if (button && button.classList) {
                button.classList.add('active');
            }

            const view = button.getAttribute('data-view');
            if (view) {
                document.querySelectorAll('.data-view').forEach(v => {
                    if (v && v.classList) {
                        v.classList.remove('active');
                    }
                });
                const viewElement = document.getElementById(`${view}-view`);
                if (viewElement && viewElement.classList) {
                    viewElement.classList.add('active');
                }
            }
        });
    });
}

async function loadDashboardStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/dashboard/stats`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const stats = await response.json();

        const statTotal = document.getElementById('stat-total');
        const statValid = document.getElementById('stat-valid');
        const statInvalid = document.getElementById('stat-invalid');
        const statScore = document.getElementById('stat-score');

        if (statTotal) statTotal.textContent = stats.total_invoices || 0;
        if (statValid) statValid.textContent = stats.valid_invoices || 0;
        if (statInvalid) statInvalid.textContent = stats.invalid_invoices || 0;
        if (statScore) statScore.textContent = (stats.average_validation_score || 0).toFixed(0);
    } catch (error) {
        console.error('Error loading dashboard stats:', error);
        // Don't show alert for dashboard stats, just log it
    }
}

async function loadInvoices() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/invoices`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        const tbody = document.getElementById('invoices-tbody');
        if (!tbody) {
            console.error('Invoices tbody not found');
            return;
        }

        tbody.innerHTML = '';

        if (!data.invoices || data.invoices.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 32px; color: var(--text-secondary);">No invoices found. Upload your first invoice to get started.</td></tr>';
            return;
        }

        data.invoices.forEach(invoice => {
            const row = document.createElement('tr');
            // Escape invoice.id to prevent XSS
            const invoiceId = String(invoice.id || '').replace(/'/g, "\\'");
            const invoiceNumber = (invoice.invoice_number || 'Invoice').replace(/'/g, "\\'");
            row.innerHTML = `
                <td>${invoice.invoice_number || '-'}</td>
                <td>${invoice.vendor_name || '-'}</td>
                <td>${invoice.buyer_name || '-'}</td>
                <td>${invoice.invoice_date || '-'}</td>
                <td>${invoice.currency || 'USD'} ${invoice.total_amount?.toFixed(2) || '0.00'}</td>
                <td><span class="status-badge-${invoice.is_valid ? 'valid' : 'invalid'}">${invoice.is_valid ? 'Valid' : 'Invalid'}</span></td>
                <td>${invoice.validation_score || 0}</td>
                <td>
                    <div class="action-buttons-row">
                        <button class="btn-view" onclick="viewInvoice('${invoiceId}')">View</button>
                        <button class="btn-delete" onclick="deleteInvoice('${invoiceId}', '${invoiceNumber.replace(/"/g, '&quot;')}')">Delete</button>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading invoices:', error);
        const tbody = document.getElementById('invoices-tbody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 32px; color: var(--text-secondary);">Error loading invoices. Please try again.</td></tr>';
        }
    }
}

async function viewInvoice(invoiceId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/invoices/${invoiceId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const invoice = await response.json();

        const mockResult = {
            success: true,
            invoice_id: invoice.id,
            validation_result: {
                invoice_id: invoice.id,
                invoice_number: invoice.invoice_number,
                is_valid: invoice.is_valid,
                score: invoice.validation_score,
                errors: invoice.validation_errors || [],
                warnings: invoice.validation_warnings || [],
                extracted_data: {
                    invoice_number: invoice.invoice_number,
                    vendor_name: invoice.vendor_name,
                    buyer_name: invoice.buyer_name,
                    vendor_address: invoice.vendor_address,
                    buyer_address: invoice.buyer_address,
                    invoice_date: invoice.invoice_date,
                    due_date: invoice.due_date,
                    currency: invoice.currency,
                    subtotal: invoice.subtotal,
                    tax_amount: invoice.tax_amount,
                    total_amount: invoice.total_amount,
                    payment_terms: invoice.payment_terms,
                    line_items: invoice.line_items || []
                }
            }
        };

        currentInvoiceData = mockResult;
        isViewingFromBatch = false; // Viewing from invoice list, not batch
        
        // Try to fetch and display the stored file
        const filename = invoice.file_name || `${invoice.invoice_number || 'invoice'}.pdf`;
        let showPreview = false;
        
        if (invoice.file_id) {
            try {
                const fileResponse = await fetch(`${API_BASE_URL}/api/invoices/${invoiceId}/file`);
                if (fileResponse.ok) {
                    const blob = await fileResponse.blob();
                    const file = new File([blob], filename, { type: blob.type });
                    currentPdfFile = file;
                    showPreview = true;
                }
            } catch (fileError) {
                console.warn('Could not load file for preview:', fileError);
                // Continue without file preview
            }
        }
        
        displayResults(mockResult, filename, showPreview);
        navigateToPage('results');
    } catch (error) {
        console.error('Error viewing invoice:', error);
        alert('Error loading invoice details');
    }
}

async function deleteInvoice(invoiceId, invoiceNumber) {
    // Confirm deletion
    const confirmed = confirm(`Are you sure you want to delete invoice "${invoiceNumber}"?\n\nThis action cannot be undone.`);
    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/invoices/${invoiceId}`, {
            method: 'DELETE',
            headers: {
                'Accept': 'application/json'
            },
            mode: 'cors'
        });

        if (!response.ok) {
            let errorMessage = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorData.message || errorMessage;
            } catch (e) {
                // If response is not JSON, use status text
                errorMessage = `${response.status} ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }

        const result = await response.json().catch(() => ({ success: true }));
        
        // Show success message
        alert(`Invoice "${invoiceNumber}" has been deleted successfully.`);
        
        // Reload invoices list
        loadInvoices();
        
        // Reload dashboard stats
        loadDashboardStats();
        
    } catch (error) {
        console.error('Error deleting invoice:', error);
        console.error('Full error details:', {
            message: error.message,
            stack: error.stack
        });
        alert(`Error deleting invoice: ${error.message || 'Unknown error occurred'}`);
    }
}

function downloadCSV() {
    if (!currentInvoiceData) {
        alert('No data to download');
        return;
    }

    const data = currentInvoiceData.validation_result.extracted_data;
    const csv = convertToCSV(data);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `invoice_${data.invoice_number || 'data'}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
}

function convertToCSV(data) {
    const headers = ['Field', 'Value'];
    const rows = [
        ['Invoice Number', data.invoice_number || ''],
        ['Vendor Name', data.vendor_name || ''],
        ['Buyer Name', data.buyer_name || ''],
        ['Invoice Date', data.invoice_date || ''],
        ['Due Date', data.due_date || ''],
        ['Currency', data.currency || ''],
        ['Subtotal', data.subtotal || ''],
        ['Tax Amount', data.tax_amount || ''],
        ['Total Amount', data.total_amount || ''],
        ['Payment Terms', data.payment_terms || '']
    ];

    let csv = headers.join(',') + '\n';
    rows.forEach(row => {
        csv += row.map(cell => `"${cell}"`).join(',') + '\n';
    });

    return csv;
}

function downloadJSON() {
    if (!currentInvoiceData) {
        alert('No data to download');
        return;
    }

    const data = currentInvoiceData.validation_result.extracted_data;
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `invoice_${data.invoice_number || 'data'}.json`;
    a.click();
    window.URL.revokeObjectURL(url);
}
