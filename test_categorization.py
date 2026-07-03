from app.services.ocr_service import classify_image_content

def test_categorization():
    test_cases = [
        {
            "desc": "Receipt",
            "text": "Store #1234\nDate: 2026-03-21\nTOTAL AMOUNT: $45.99\nThank you for shopping!",
            "kws": [("total", 1, False), ("amount", 1, False), ("date", 1, False)]
        },
        {
            "desc": "Code Snippet",
            "text": "def process_image(db: Session, image_id: int):\n    image = db.query(Image).first()\n    return True",
            "kws": [("def", 1, False), ("process_image", 1, False), ("return", 1, False)]
        },
        {
            "desc": "Document",
            "text": "This agreement is entered into as of the date signed below. Terms and conditions apply.",
            "kws": [("agreement", 1, False), ("terms", 1, False), ("conditions", 1, False)]
        }
    ]

    print("=== Testing Categorization Logic ===")
    for test in test_cases:
        cat, conf = classify_image_content(test["text"], test["kws"])
        print(f"Test Case: {test['desc']}")
        print(f"  Result: {cat} (Conf: {conf:.2f})")
        if cat == test["desc"]:
            print(f"  ✅ Correct")
        else:
            print(f"  ❌ Expected {test['desc']} but got {cat}")
        print("-" * 30)

if __name__ == "__main__":
    test_categorization()
