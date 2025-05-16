document.addEventListener("DOMContentLoaded", () => {
    const textInput = document.getElementById("textInput");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const fileUpload = document.getElementById("fileUpload");
    const micButton = document.getElementById("micButton");
    const resultArea = document.getElementById("resultArea");
    const copyBtn = document.getElementById("copyBtn");
    
    // Notification yaratish funksiyasi
    const notification = (() => {
        const div = document.createElement('div');
        div.id = 'copyNotification';
        Object.assign(div.style, {
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            padding: '10px 15px',
            backgroundColor: '#4CAF50',
            color: 'white',
            borderRadius: '5px',
            fontWeight: 'bold',
            display: 'none',
            zIndex: '9999',
        });
        document.body.appendChild(div);
        return div;
    })();

    // So'zlar limitini tekshirish va cheklash funksiyasi
    function limitWords(text, max = 100) {
        const words = text.trim().split(/\s+/);
        if (words.length > max) {
            alert(`Matnda ${max} so'zdan ortiq kiritib bo‘lmaydi.`);
            return words.slice(0, max).join(' ') + ' ';
        }
        return text;
    }

    // TextInput input event
    textInput.addEventListener('input', () => {
        textInput.value = limitWords(textInput.value);
    });

    // Mikrafon ovozini aniqlash
    let recognition;
    if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.lang = 'uz-UZ';
        recognition.continuous = false;
        recognition.interimResults = false;

        micButton.addEventListener('click', () => {
            if (micButton.classList.contains('recording')) {
                recognition.stop();
            } else {
                recognition.start();
            }
        });

        recognition.onstart = () => micButton.classList.add('recording');
        recognition.onend = () => micButton.classList.remove('recording');
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            textInput.value = limitWords(textInput.value + transcript + ' ');
        };
    } else {
        micButton.disabled = true;
        micButton.title = "Sizning brauzeringiz ovozli kiritishni qo'llab-quvvatlamaydi";
    }

    // Natijani Clipboard ga nusxalash
    copyBtn.addEventListener('click', () => {
        if (resultArea.innerText.trim()) {
            navigator.clipboard.writeText(resultArea.innerText).then(() => {
                notification.textContent = "Nusxalandi!";
                notification.style.display = 'block';
                setTimeout(() => {
                    notification.style.display = 'none';
                }, 2000);
            }).catch(() => {
                alert("Clipboardga nusxalashda xatolik yuz berdi");
            });
        }
    });

    // Fayl yuklash
    fileUpload.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const allowedTypes = [
            'text/plain',
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        ];
        if (!allowedTypes.includes(file.type)) {
            alert("Faqat .txt, .pdf, .docx va .pptx formatlari qabul qilinadi");
            fileUpload.value = '';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            displayResult(data.correctedHtml || data.correctedText, data.errorWords || [], data.suggestionsMap || {});
            textInput.value = data.correctedText || "";
        })
        .catch(() => alert("Faylni yuklashda xatolik yuz berdi"));
    });

    // Matnni tahlil qilish tugmasi
    analyzeBtn.addEventListener('click', () => {
        const text = textInput.value.trim();
        if (!text) {
            alert("Iltimos, matn kiriting!");
            return;
        }

        if (text.split(/\s+/).length > 100) {
            alert("Iltimos, 100 so'zdang ortiq matn kiritmang.");
            return;
        }

        fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        })
        .then(res => res.json())
        .then(data => {
            displayResult(data.correctedHtml || data.correctedText, data.errorWords || [], data.suggestionsMap || {});
        })
        .catch(err => alert("Xatolik yuz berdi: " + err.message));
    });

    // Natijani ko'rsatish
    function displayResult(text, errorWords = [], suggestionsMap = {}) {
        resultArea.innerHTML = '';

        if (!errorWords.length) {
            resultArea.textContent = text;
            return;
        }

        if (text.includes('<span')) {
            resultArea.innerHTML = text;
            resultArea.querySelectorAll('.error-word').forEach(span => {
                span.addEventListener('click', () => {
                    const word = span.textContent.trim().toLowerCase();
                    const suggestions = suggestionsMap[word] || [];
                    showSuggestions(span, suggestions);
                });
            });
            return;
        }

        const words = text.split(/\s+/);
        words.forEach(word => {
            const cleanWord = word.replace(/[.,!?;:"“”‘’]/g, "").toLowerCase();
            if (errorWords.includes(cleanWord)) {
                const span = document.createElement('span');
                span.className = 'error-word';
                span.textContent = word + ' ';
                span.setAttribute('data-suggestions', (suggestionsMap[cleanWord] || []).join(','));
                span.addEventListener('click', () => {
                    const suggStr = span.getAttribute('data-suggestions') || "";
                    const suggestions = suggStr ? suggStr.split(',') : [];
                    showSuggestions(span, suggestions);
                });
                resultArea.appendChild(span);
            } else {
                resultArea.appendChild(document.createTextNode(word + ' '));
            }
        });
    }

    // Taklif oynasini ko'rsatish
    function showSuggestions(targetSpan, suggestions) {
        closeSuggestions();
        if (!suggestions.length) return;

        const box = document.createElement('div');
        box.className = 'suggestion-box';

        suggestions.forEach(sugg => {
            const div = document.createElement('div');
            div.textContent = sugg;
            div.addEventListener('click', () => {
                replaceWord(targetSpan, sugg);
                closeSuggestions();
            });
            box.appendChild(div);
        });

        const rect = targetSpan.getBoundingClientRect();
        const containerRect = resultArea.getBoundingClientRect();

        box.style.position = 'absolute';
        box.style.top = (rect.bottom - containerRect.top + window.scrollY) + 'px';
        box.style.left = (rect.left - containerRect.left + window.scrollX) + 'px';

        document.body.appendChild(box);

        function onClickOutside(e) {
            if (!box.contains(e.target) && e.target !== targetSpan) {
                closeSuggestions();
                document.removeEventListener('click', onClickOutside);
            }
        }
        document.addEventListener('click', onClickOutside);
    }

    // Taklif oynasini yopish
    function closeSuggestions() {
        const existing = document.querySelector('.suggestion-box');
        if (existing) existing.remove();
    }

    // So'zni almashtirish
    function replaceWord(span, newWord) {
        span.textContent = newWord + ' ';
        span.classList.remove('error-word');
        span.removeAttribute('data-suggestions');
    }
});
