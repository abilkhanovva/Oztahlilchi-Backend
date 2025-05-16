import os
import docx
import PyPDF2
from pptx import Presentation
from rapidfuzz import process
from bs4 import BeautifulSoup

def sanitize_for_telegram(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "html.parser")
    for span in soup.find_all("span", class_="error-word"):
        new_tag = soup.new_tag("b")
        new_tag.string = span.get_text()
        span.replace_with(new_tag)
    if soup.body:
        return str(soup.body.decode_contents())
    return str(soup)

# 📂 Bazani yuklash funksiyasi
def load_database():
    base_dir = "C:\\Users\\User\\Desktop\\OzTahlilchi"
    latin = set()
    fully = set()

    with open(os.path.join(base_dir, "latin_baza.txt"), "r", encoding="utf-8") as f:
        latin.update(word.strip().lower() for word in f)

    with open(os.path.join(base_dir, "fully_baza.txt"), "r", encoding="utf-8") as f:
        fully.update(word.strip().lower() for word in f)

    return latin.union(fully)

# 📌 Umumiy baza
DATABASE = load_database()

# 🧠 Matnni tahlil qilish funksiyasi (takliflar optimallashtirilgan)
def analyze_text(text, max_suggestions=3, similarity_threshold=70, min_length_ratio=0.7):
    words = text.strip().replace("\n", " ").split()
    corrected_words = []
    error_words = []
    suggestions_map = {}

    for word in words:
        clean_word = word.strip(".,?!;:()[]{}\"'«»").lower()

        if clean_word in DATABASE:
            corrected_words.append(word)
        else:
            error_words.append(clean_word)

            # 10 ta o‘xshash so‘zdan uzunligi mos keladiganlarini tanlab, eng yaxshilarini olib qolamiz
            matches = process.extract(
                clean_word,
                DATABASE,
                limit=10,
                score_cutoff=similarity_threshold
            )

            filtered = [
                match[0]
                for match in matches
                if len(match[0]) >= len(clean_word) * min_length_ratio
            ][:max_suggestions]

            suggestions_map[clean_word] = filtered
            # HTML orqali noto‘g‘ri so‘zga span qo‘shamiz
            safe_suggestions = ",".join(filtered) if filtered else ""
            corrected_words.append(
                f'<span class="error-word" data-suggestions="{safe_suggestions}">{word}</span>'
            )

    corrected_text = " ".join(corrected_words)
    return corrected_text, error_words, suggestions_map

# 📤 Fayldan matn ajratish funksiyasi
def extract_text_from_file(file):
    filename = file.filename
    ext = filename.split(".")[-1].lower()

    try:
        if ext == "txt":
            return file.read().decode("utf-8")

        elif ext == "docx":
            doc = docx.Document(file)
            return "\n".join([p.text for p in doc.paragraphs])

        elif ext == "pdf":
            reader = PyPDF2.PdfReader(file)
            return "\n".join(page.extract_text() for page in reader.pages if page.extract_text())

        elif ext == "pptx":
            prs = Presentation(file)
            text = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text.append(shape.text)
            return "\n".join(text)
    except Exception as e:
        print(f"[Xatolik] Faylni o‘qishda muammo: {e}")

    return ""
