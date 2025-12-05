# Frontend - Invoicely Web Application

## Quick Start

Serve the frontend using Python:

```bash
python -m http.server 3000
```

Or using Node.js:

```bash
npx http-server -p 3000
```

Then open http://localhost:3000 in your browser.

## Features

### Dashboard
- View statistics overview (total invoices, valid/invalid counts, average score)
- Quick access to processing and invoice browsing

### Upload & Process
- **Single file upload**: Drag-and-drop or click to upload
- **Batch upload**: Select multiple files (Ctrl+Click / Shift+Click or drag multiple)
- **Supported formats**: PDF only
- **Real-time progress**: Visual indicators during processing
- **Batch summary**: View success/failure counts and download results

### Extraction Results
- View extracted invoice data in **Refined View** (formatted display) or **JSON View** (raw data)
- Display all extracted fields (invoice number, vendor, buyer, amounts, dates, etc.)
- **File preview** with zoom controls (PDF.js)
- Navigation controls for multi-page documents
- **Keyboard shortcuts**: 
  - `Ctrl/Cmd + +/-` for zoom
  - `Ctrl/Cmd + 0` for fit to page
  - `Ctrl/Cmd + Left/Right` for page navigation
- Download results as CSV or JSON
- Batch results navigation with back button

### All Invoices
- Browse all processed invoices in paginated table
- View validation status with color-coded badges
- Expand rows to see detailed information
- Click "View" to see full extraction and validation results
- Click "Delete" to remove invoices

### Dark Theme
- **Toggle button**: Theme switcher in top-right header (sun/moon icon)
- **Persistent**: Theme preference saved to browser localStorage
- **Pitch-black dark mode**: #0A0A0A background for reduced eye strain
- **High contrast**: WCAG AA compliant contrast ratios
- **Full support**: All components styled for light and dark modes
- **Accessibility**: Respects system preferences (can be extended)

## Configuration

Edit `app.js` and update `API_BASE_URL` if your backend runs on a different address:

```javascript
const API_BASE_URL = 'http://localhost:8000';
```

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Architecture

### Technology Stack
- **Framework**: Vanilla JavaScript (no dependencies)
- **Styling**: CSS with custom properties (CSS variables) for theming
- **File Preview**: PDF.js for PDF rendering with zoom and page navigation
- **API Integration**: Fetch API for async communication with backend

### File Structure
- `index.html` - Single-page application with all views
- `styles.css` - Complete styling with responsive design and dark theme
- `app.js` - JavaScript logic (API calls, UI interactions, state management)

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + +` | Zoom in file preview |
| `Ctrl/Cmd + -` | Zoom out file preview |
| `Ctrl/Cmd + 0` | Fit file to page |
| `Ctrl/Cmd + Left` | Previous page (PDF) |
| `Ctrl/Cmd + Right` | Next page (PDF) |

## Performance Tips

- The frontend communicates with the API asynchronously
- Large batch uploads (>20 files) may take time - use the progress indicator
- File size limit: 35MB per file
- Batch limit: 50 files maximum per upload

## Troubleshooting

### "Cannot connect to backend API"
- Ensure backend API is running on `http://localhost:8000`
- Update `API_BASE_URL` in `app.js` if backend is on different address
- Check browser console for CORS errors

### "File preview not loading"
- Ensure browser has PDF.js support for PDF viewing
- Try refreshing the page
- Large files may take longer to preview

### "Dark theme not persisting"
- Ensure browser localStorage is enabled
- Check browser developer tools > Application > Local Storage
