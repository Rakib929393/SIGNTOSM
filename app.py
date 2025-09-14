import os
import logging
import io
import random
from flask import Flask, request, jsonify, send_from_directory, url_for, render_template
from pypdf import PdfReader
from PIL import Image

# =======================
# Flask App Configuration
# =======================
app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
EXTRACTED_FOLDER = os.path.join(os.getcwd(), "images")
ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB limit

# Flask JSON settings
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
app.config["JSON_AS_ASCII"] = False  

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXTRACTED_FOLDER, exist_ok=True)

# =======================
# Helper Functions
# =======================
def generate_random_number(length=30):
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_images_from_pdf(pdf_file_path: str, output_path: str):
    extracted_files = []
    try:
        reader = PdfReader(pdf_file_path)
        seen_images = set()
        image_count = 0

        for page in reader.pages:
            for image in page.images:
                image_data = image.data
                image_hash = hash(image_data)
                if image_hash in seen_images:
                    continue
                seen_images.add(image_hash)

                ext = os.path.splitext(image.name)[1].lower()

                # Convert JP2/JPEG2000 to PNG
                if ext in [".jp2", ".jpx"]:
                    try:
                        with Image.open(io.BytesIO(image_data)) as img:
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            img_bytes = io.BytesIO()
                            img.save(img_bytes, format="PNG")
                            image_data = img_bytes.getvalue()
                            ext = ".png"
                    except Exception as e:
                        logging.error(f"JP2 Conversion Failed: {e}")
                        continue

                # Naming logic
                random_number = generate_random_number()
                if image_count == 0:
                    filename = f"user-img-{random_number}{ext}"
                elif image_count == 1:
                    filename = f"sign-img-{random_number}{ext}"
                else:
                    filename = f"{random_number}{ext}"

                file_path = os.path.join(output_path, filename)
                with open(file_path, "wb") as fp:
                    fp.write(image_data)

                extracted_files.append(filename)
                image_count += 1

    except Exception as e:
        logging.error(f"Failed to extract images: {e}")
    
    return extracted_files

def make_response(data: dict, status=200):
    """Attach TG_Channel and return JSON response"""
    data["TG_Channel"] = "@UNKNOWN_X_1337_BOT"
    return jsonify(data), status

# =======================
# Routes
# =======================
@app.route("/")
def home():
    return make_response({"status": "Images Extractor Active"})

@app.route("/images", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return make_response({"error": "No file part"}, 400)

    file = request.files["file"]
    if file.filename == "":
        return make_response({"error": "No selected file"}, 400)

    if not allowed_file(file.filename):
        return make_response({"error": "Invalid file type"}, 400)

    # Check file size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return make_response({"error": "File size exceeds 2 MB limit"}, 400)

    # Save temporarily
    pdf_filename = f"{generate_random_number()}.pdf"
    pdf_path = os.path.join(UPLOAD_FOLDER, pdf_filename)
    file.save(pdf_path)

    # Extract images
    extracted_images = extract_images_from_pdf(pdf_path, EXTRACTED_FOLDER)

    # Delete PDF after extraction
    try:
        os.remove(pdf_path)
    except Exception as e:
        logging.error(f"Failed to delete PDF: {e}")

    if extracted_images:
        images_dict = {}
        if len(extracted_images) >= 1:
            images_dict["user-image"] = url_for("download_file", filename=extracted_images[0], _external=True)
        if len(extracted_images) >= 2:
            images_dict["sign-image"] = url_for("download_file", filename=extracted_images[1], _external=True)
        if len(extracted_images) > 2:
            images_dict["extra-images"] = [url_for("download_file", filename=f, _external=True) for f in extracted_images[2:]]

        return make_response({
            "message": "Images extracted successfully",
            "totalImages": str(len(extracted_images)),
            "images": images_dict
        })

    return make_response({"message": "No images found in the PDF"})

@app.route("/images/<filename>")
def download_file(filename):
    return send_from_directory(EXTRACTED_FOLDER, filename, as_attachment=True)

@app.route("/upload")
def upload_page():
    return render_template("index.html")

# =======================
# Main
# =======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
