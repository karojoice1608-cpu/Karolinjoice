import re
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Image, User
from app.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("admin.html", {"request": request, "username": user.username})

@router.get("/api/admin/bills")
def get_parsed_bills(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    images = db.query(Image).filter(Image.user_id == user.id, Image.status == "completed").order_by(Image.id.desc()).all()
    results = []
    
    # Matches common price formats: 12.99, $12.99, Rs. 12.99, 12,99
    price_pattern = re.compile(r'(?:\$|Rs\.?|₹|€|£)?\s*\d+[.,]\d{2}\s*(?:\$|€|£)?')
    
    for img in images:
        texts = sorted(img.extracted_texts, key=lambda t: t.bbox_y)
        lines = []
        current_line = []
        current_y = None
        tolerance = 0.02  # Merge items within 2% vertical offset
        
        for t in texts:
            if current_y is None:
                current_y = t.bbox_y
                current_line.append(t)
            elif abs(t.bbox_y - current_y) < tolerance:
                current_line.append(t)
            else:
                lines.append(current_line)
                current_line = [t]
                current_y = t.bbox_y
        if current_line:
            lines.append(current_line)
            
        items = []
        s_no = 1
        for line in lines:
            # Sort horizontally
            line = sorted(line, key=lambda t: t.bbox_x)
            line_text = " ".join([t.text_content for t in line])
            
            prices = price_pattern.findall(line_text)
            if prices:
                price_str = prices[-1]
                product_str = line_text.replace(price_str, "").strip()
                product_str = re.sub(r'[^a-zA-Z0-9\s]$', '', product_str).strip()
                
                # Exclude purely metadata lines like "Total", "Tax", etc. via fuzzy match
                is_metadata = re.search(r'^(total|subtotal|tax|change|cash|card|due|balance|visa|mastercard|amount)\b', product_str, re.IGNORECASE)
                
                if product_str and len(product_str) > 1 and not is_metadata:
                    items.append({
                        "s_no": s_no,
                        "product": product_str,
                        "price": price_str
                    })
                    s_no += 1
                    
        results.append({
            "image_id": img.id,
            "title": img.original_name,
            "items": items
        })
        
    return {"bills": results}
