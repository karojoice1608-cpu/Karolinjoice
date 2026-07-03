# ⚡ Screendex — AI-Powered Image Indexing & Search System

> **MCA Project** | Python FastAPI · PostgreSQL · EasyOCR · NLTK · Deep Learning

---

## 📌 Project Title Breakdown

| Component | Meaning |
|-----------|---------|
| **Screen** | Screenshots, screen captures, digital images |
| **dex** (Index) | Indexed, searchable database organization |
| **AI-Powered** | CNN-based text detection + EasyOCR + NLP |
| **Indexing System** | Converts extracted text → structured PostgreSQL keyword index |
| **Search System** | Keyword-based retrieval with relevance ranking (0–100%) |
| **Born-Digital Images** | Screenshots, WhatsApp captures, digital receipts — clean, machine-readable text |
| **Scene Text Images** | Real-world photos of signboards, printed documents — challenging lighting, perspective |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      SCREENDEX PIPELINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  [User Upload]                                                    │
│       │                                                           │
│       ▼                                                           │
│  [FastAPI Backend] ──────────────────────────────────────────┐   │
│       │                                                       │   │
│       ▼                                                       │   │
│  [Pre-Processing]                                             │   │
│   - Grayscale conversion                                      │   │
│   - Noise removal (fastNlMeansDenoising)                      │   │
│   - Adaptive thresholding                                     │   │
│       │                                                       │   │
│       ▼                                                       │   │
│  [Text Detection — CNN]                                       │   │
│   - EasyOCR (CRAFT architecture)                              │   │
│   - Detects text regions → bounding boxes                     │   │
│   - Handles both Born-Digital & Scene Text                    │   │
│       │                                                       │   │
│       ▼                                                       │   │
│  [OCR Extraction]                                             │   │
│   - EasyOCR / Tesseract fallback                             │   │
│   - Per-region confidence scores (0.0–1.0)                    │   │
│   - Relative bounding box coordinates                         │   │
│       │                                                       │   │
│       ▼                                                       │   │
│  [NLP Processing]                                             │   │
│   - Text cleaning (noise removal)                             │   │
│   - Tokenization (NLTK word_tokenize)                         │   │
│   - Stopword removal                                          │   │
│   - Porter Stemming (run→running→run)                         │   │
│   - Keyword frequency counting                                │   │
│       │                                                       │   │
│       ▼                                                       │   │
│  [PostgreSQL Database Index]                                  │   │
│   - images table (metadata)                                   │   │
│   - extracted_texts table (text regions + bbox + confidence)  │   │
│   - keywords table (keyword + frequency index)                │   │
│       │                                                       │   │
│       ▼                                                       │   │
│  [Search Engine]                                              │   │
│   - Keyword table scan (fast path)                            │   │
│   - Full-text ILIKE scan (high recall)                        │   │
│   - Relevance scoring: 0.6×kw_score + 0.4×confidence         │   │
│   - Results ranked by relevance %                             │   │
│       │                                                       │   │
│       ▼                                                       │   │
│  [Frontend Results]                                           │   │
│   - Image cards with relevance score                          │   │
│   - Highlighted matching snippets                             │   │
│   - Bounding box overlays on image                            │   │
│   - Autocomplete suggestions                                  │   │
└───────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

| Layer | Technology | Why This Choice |
|-------|------------|-----------------|
| **Backend Framework** | Python FastAPI | Async processing, auto-generates API docs, type validation |
| **OCR Engine** | EasyOCR (+ Tesseract fallback) | Handles both printed & scene text; GPU/CPU flexible |
| **Text Detection Model** | CRAFT (CNN-based) via EasyOCR | State-of-art character region detection |
| **Image Pre-processing** | OpenCV | Industry standard for computer vision pre-processing |
| **NLP** | NLTK | Tokenization, stopwords, stemming for keyword quality |
| **Database** | PostgreSQL | ACID compliance, full-text search, indexed queries |
| **ORM** | SQLAlchemy | Pythonic DB access, migration support |
| **Frontend** | Vanilla HTML/CSS/JS | No framework dependency, fast loading |
| **Server** | Uvicorn (ASGI) | Async event loop, high concurrency |

---

## 📂 Project Structure

```
screendex/
├── main.py                     # FastAPI app entry point
├── run.py                      # Quick-start script
├── setup_db.py                 # Database setup script
├── requirements.txt            # Python dependencies
├── .env                        # Configuration (DB URL, etc.)
│
├── app/
│   ├── database.py             # SQLAlchemy engine & session
│   ├── schemas.py              # Pydantic request/response models
│   │
│   ├── models/
│   │   └── models.py           # DB tables: Image, ExtractedText, Keyword
│   │
│   ├── routers/
│   │   ├── images.py           # Upload, list, detail, delete endpoints
│   │   └── search.py           # Search, suggest, stats endpoints
│   │
│   └── services/
│       ├── ocr_service.py      # OCR extraction + NLP keyword extraction
│       └── image_service.py    # Full pipeline orchestration
│
├── templates/
│   ├── index.html              # Search home page
│   ├── upload.html             # Upload page
│   ├── gallery.html            # Gallery page
│   └── image_detail.html       # Individual image detail
│
└── static/
    ├── css/style.css           # Main stylesheet
    ├── js/
    │   ├── search.js           # Search page logic
    │   ├── upload.js           # Upload + processing pipeline display
    │   ├── gallery.js          # Gallery page logic
    │   └── detail.js           # Image detail + bbox overlay
    └── uploads/                # Uploaded images (auto-created)
        └── thumbnails/         # Generated thumbnails
```

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.9+
- PostgreSQL 13+
- pip

### Step 1: Clone & Install Dependencies

```bash
git clone <repo-url>
cd screendex
pip install -r requirements.txt
```

### Step 2: Configure Environment

Edit `.env`:
```env
DATABASE_URL=postgresql://screendex_user:screendex_pass@localhost:5432/screendex_db
```

### Step 3: Setup Database

```bash
# Option A: Automatic (requires postgres superuser)
python setup_db.py

# Option B: Manual PostgreSQL commands
psql -U postgres
CREATE USER screendex_user WITH PASSWORD 'screendex_pass';
CREATE DATABASE screendex_db OWNER screendex_user;
GRANT ALL PRIVILEGES ON DATABASE screendex_db TO screendex_user;
\q

python setup_db.py --skip-db-create
```

### Step 4: Run the Application

```bash
python run.py
# OR
uvicorn main:app --reload --port 8000
```

### Step 5: Access

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | Search interface |
| `http://localhost:8000/upload` | Upload images |
| `http://localhost:8000/gallery` | View all images |
| `http://localhost:8000/api/docs` | Interactive API documentation |

---

## 🔌 API Endpoints

### Images
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/images/upload` | Upload single image |
| POST | `/api/images/upload-batch` | Upload up to 20 images |
| GET  | `/api/images/` | List all images |
| GET  | `/api/images/{id}` | Get image with extracted text |
| GET  | `/api/images/{id}/status` | Poll processing status |
| POST | `/api/images/{id}/reprocess` | Re-run OCR pipeline |
| DELETE | `/api/images/{id}` | Delete image and data |

### Search
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/search/?q=python+error` | Search images |
| GET | `/api/search/suggest?q=py` | Autocomplete suggestions |
| GET | `/api/search/stats` | System statistics |

### Search Example Response
```json
{
  "query": "CNN architecture",
  "total_results": 3,
  "page": 1,
  "page_size": 12,
  "results": [
    {
      "id": 42,
      "filename": "lecture_notes.png",
      "relevance_score": 92.3,
      "matched_snippets": ["Explain **CNN** **architecture** in deep learning..."],
      "text_regions": [
        {"x": 0.1, "y": 0.25, "width": 0.8, "height": 0.05,
         "text": "CNN architecture", "confidence": 0.94}
      ]
    }
  ]
}
```

---

## 💡 Real-World Use Cases

### 1. Student — Screenshot Study Notes
> Upload 500 lecture screenshots → Search "gradient descent" → Instantly find all slides discussing it.

### 2. Researcher — Paper Collection
> Upload photos of printed papers → Search "transformer attention" → All relevant pages highlighted.

### 3. Legal Firm — Document Evidence
> 1,000 scanned document images → Search "contract violation" → Specific documents found in seconds, not hours.

### 4. Business — Receipt Management
> Digital receipts from various apps → Search "restaurant" or a vendor name → All matching receipts retrieved.

---

## 🎓 Interview Q&A Guide

**Q: What problem does Screendex solve?**
> Traditional photo galleries only search by metadata (date, location). Screendex enables *content-based* search — you can find any image by the text visible inside it, even if that text is handwritten on a whiteboard or printed on a receipt photographed at an angle.

**Q: How does the OCR pipeline work?**
> Image → OpenCV pre-processing (denoise, threshold) → EasyOCR's CRAFT model detects text regions using CNNs → OCR extracts text with confidence scores → NLTK tokenizes and stems keywords → PostgreSQL stores the keyword index for fast retrieval.

**Q: Why FastAPI over Flask/Django?**
> FastAPI is async-native, meaning multiple OCR jobs can process concurrently without blocking. It auto-generates Swagger API documentation and uses Pydantic for strict type validation — essential for a production-grade API.

**Q: What's the difference between Born-Digital and Scene Text?**
> Born-Digital images (screenshots) have clean, consistent fonts with no lighting variation — standard OCR handles them well. Scene Text (real-world photos) has perspective distortion, shadows, varied fonts, and background complexity — requiring CNN-based detection before OCR.

**Q: How is relevance scoring calculated?**
> Score = 0.6 × keyword_frequency_ratio + 0.4 × OCR_confidence + 0.1 if_text_region_match. This weighs both how frequently the keyword appears in the image and how confident the OCR engine was in extracting it.

**Q: How does the system scale?**
> PostgreSQL B-tree indexes on the keyword column enable O(log n) lookups. Background task processing via FastAPI's BackgroundTasks prevents upload blocking. The architecture supports horizontal scaling with connection pooling.

---

## 📊 Database Schema

```sql
-- Images table
CREATE TABLE images (
    id              SERIAL PRIMARY KEY,
    filename        VARCHAR(255) NOT NULL,
    original_name   VARCHAR(255) NOT NULL,
    file_path       VARCHAR(500) NOT NULL,
    file_size       INTEGER,
    image_type      VARCHAR(20),   -- born_digital | scene_text
    width           INTEGER,
    height          INTEGER,
    status          VARCHAR(20),   -- pending | processing | completed | failed
    uploaded_at     TIMESTAMP DEFAULT NOW(),
    processed_at    TIMESTAMP,
    error_message   TEXT,
    thumbnail_path  VARCHAR(500)
);

-- Extracted text regions
CREATE TABLE extracted_texts (
    id           SERIAL PRIMARY KEY,
    image_id     INTEGER REFERENCES images(id) ON DELETE CASCADE,
    text_content TEXT NOT NULL,
    confidence   FLOAT,           -- OCR confidence 0.0–1.0
    bbox_x       FLOAT,           -- relative position 0–1
    bbox_y       FLOAT,
    bbox_width   FLOAT,
    bbox_height  FLOAT,
    text_order   INTEGER          -- reading order
);

-- Keyword index
CREATE TABLE keywords (
    id          SERIAL PRIMARY KEY,
    image_id    INTEGER REFERENCES images(id) ON DELETE CASCADE,
    keyword     VARCHAR(255) NOT NULL,  -- INDEXED
    frequency   INTEGER DEFAULT 1,
    is_stopword BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_keyword ON keywords(keyword);  -- Fast keyword lookup
CREATE INDEX idx_kw_image ON keywords(image_id);
```

---

## 🔮 Future Enhancements

- **Semantic Search**: Sentence-BERT embeddings for concept-based search ("find images about machine learning" without exact keyword match)
- **Language Support**: Multi-language OCR (Hindi, Tamil, etc.)  
- **Handwriting Recognition**: HTR models for handwritten notes
- **Export**: PDF report generation of search results
- **User Accounts**: Multi-user support with private image collections

---

*Screendex v1.0 — MCA Final Year Project*
