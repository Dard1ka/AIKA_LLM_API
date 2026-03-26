#AIKA LLM API 
An API-based AI system that integrates OpenAI’s language models, text-to-speech using Edge TTS, and voice conversion based on RVC. The system accepts user input, generates a text response via an LLM, then converts it to speech using TTS and applies a specific voice (fine-tuned voice) to provide a better interactive experience.

📂 File Structure
```pqsql
AIKA_LLM_API/
│── data/
│── frontend/
│── memory/
│── model_source/
│── rvc_engine/
│── cookies.json
│── server.py                 
│── migrate.py        
│── requirements_memory.txt
│── requirements_rvc_engine.txt
│── rvc_convert.py
│── tts_base.py

```
System Pipeline

  User Input → LLM API → Text Response → TTS API → RVC → Final Voice Output

Key Features
- Real API-based conversational AI
- Voice-enabled AI interaction (text → speech → character voice)
- Context-aware memory system (long-term & short-term)
- Modular architecture for integrating various AI services
- Scalable system (can upgrade models without changing the core system)


How to run this project : 
1. Decide which voice model you want to fine-tune first (Recommend using a .pth file) or use the model that i use is in this link (Hutao Voice):
   https://drive.google.com/drive/folders/1CajoMW1VfkmhOYESQo3XHhlHi63WujtG?usp=sharing
   And put in on model_source folder for index, rvc_engine/assets/weights for model.pth
2. ```bash
    git clone https://github.com/Dard1ka/AIKA_LLM_API.git 
    git clone https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI rvc_engine
   ```
3. Create & Install 2 environments : memory (for backend) & rvc_engine
   ```bash
    pip install -r requirements_memory.txt
    pip install -r requirements_rvc_engine.txt
   ```
4. Create .env file and fill down :
   ```bash
   OPENAI_API_KEY= .....
   MODEL=....
   TMP_AUDIO_DIR=tmp_audio
   RVC_ROOT=/rvc_engine
   RVC_DEVICE=cuda
   RVC_URL=http://127.0.0.1:7865 or change with your local after run rvc_engine
   ```
5. Activate the environments and run :
   memory :
   ```bash
    uvicorn server:app --reload --port 8000
   ```
   rvc_engine :
   ```bash
    python infer-web.py
   ```
   in frontend folder :
    ```bash
    npm install
    npm run dev
   ```
