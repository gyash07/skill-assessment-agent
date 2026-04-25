<!-- To start the code run this in virtual environment terminal: -->
    streamlit run app.py

<!-- to check for the models i can use through API -->
python -c "import google.generativeai as genai; genai.configure(api_key='AIzaSyBfeHo-wB7-NkLuare7WfgKg5W82OUoZAk'); [print(m.name) for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]"