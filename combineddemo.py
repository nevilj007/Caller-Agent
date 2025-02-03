from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
from fastapi.responses import HTMLResponse, FileResponse
from typing import Dict, Any, List
from phi.agent import Agent
from phi.model.google import Gemini
from phi.storage.agent.postgres import PgAgentStorage
import openpyxl
from openpyxl import Workbook

import os
#instruction:"Present the generated prompt to the user for final approval",
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory storage for conversations
conversations: Dict[str, Dict[str, Any]] = {}

# Initialize the agent for prompt generation
db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"
prompt = {}


def prompt_generator(user_message: str, caller_id: str):
    if caller_id not in prompt:
        prompt[caller_id] = Agent(
            name="Prompt Generator",
            model=Gemini(
                id="gemini-2.0-flash-exp",
                api_key="AIzaSyDB07klOR53olXgSBf9iKTDH-rzzjJcRYQ"
            ),
            storage=PgAgentStorage(table_name=f"assistant{[caller_id]}", db_url=db_url),
            search_knowledge=True,
            read_chat_history=True,
            num_history_responses=10,
            add_history_to_messages=True,
            description="An agent that generates prompts for a caller agent to interact with customers",
            instructions=[
                "Ask questions one by one, not as a paragraph",
                "Ask the user for specific details about the caller agent's purpose",
                "Inquire about the target audience or customer type",
                "Request information about the desired tone and style of communication",

                "Ask for any specific points or topics that must be covered",
                "Take suggestions from the user for improvements or modifications",
                "When the user indicates they are satisfied, generate a comprehensive prompt based on the gathered information",

                "once you are asked to generate prompt,Generate only the prompt content when requested. Do not include extra text or context like 'Are you satisfied?' or 'Here is your prompt."
            ],
            debug_mode=True
        )
    response = prompt[caller_id].run(user_message)
    return response.content


class Transcript(BaseModel):
    id: int
    created_at: str
    text: str
    user: str


class WebhookData(BaseModel):
    call_id: str
    transcripts: List[Transcript]
    concatenated_transcript: str
    summary: str
    call_length: float
    price: float


class Message(BaseModel):
    message: str


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})


@app.post("/make_call")
async def make_call(
        phone_number: str = Form(...),
        questions: str = Form(...),
        knowledge_base_url: str = Form(...),
        prompt: str = Form(...)
):
    headers = {
        'authorization': 'org_cf32ff78fea328fb1b37b1e5330f896c446a5686f7996d04e46e8183a2ef173e4f6f36781573c2f152a269'
    }

    question_list = questions.split('\n')

    data = {
        'phone_number': phone_number,
        'task': f"Introduce yourself as assistant from Samajh ai. strictly follow{prompt} style for conversation.Ask the following questions one by one: {question_list}.if user asks any question out of context refer {knowledge_base_url} to answer it",
        'knowledge_base': knowledge_base_url,
        'webhook': 'https://6b1c-2409-40f3-e-814b-d011-79d7-84a1-ff2a.ngrok-free.app/webhook',
        'record': True,
        'reduce_latency': True,
        'amd': True
    }

    response = requests.post('https://api.bland.ai/v1/calls', json=data, headers=headers)
    return {"message": "Call initiated", "call_id": response.json().get('call_id'), "phone number": phone_number,
            "question": question_list}


@app.post("/webhook")
async def webhook(data: WebhookData):
    call_id = data.call_id
    if call_id:
        conversations[call_id] = {
            'transcripts': data.transcripts,
            'concatenated_transcript': data.concatenated_transcript,
            'summary': data.summary,
            'call_length': data.call_length,
            'price': data.price
        }
        # Create Excel file
        wb = Workbook()
        ws = wb.active
        ws.title = f"Call_{call_id}"

        # Add headers
        ws.append(["Timestamp", "Speaker", "Text"])

        # Add transcript data
        for transcript in data.transcripts:
            ws.append([transcript.created_at, transcript.user, transcript.text])

        # Add summary
        ws.append([])
        ws.append(["Summary", data.summary])

        # Add call details
        ws.append([])
        ws.append(["Call Length", f"{data.call_length} minutes"])
        ws.append(["Price", f"${data.price}"])

        # Save the Excel file
        filename = f"call_{call_id}.xlsx"
        wb.save(filename)
        return {"status": "received", "message": f"Conversation saved for call_id: {call_id}","excel_file": filename}
    else:
        return {"status": "error", "message": "No call_id provided"}


@app.get("/conversation/{call_id}")
async def get_conversation(call_id: str):
    conversation = conversations.get(call_id)
    if conversation:
        return conversation
    return {"error": "Conversation not found"}
@app.get("/prompt_generator")
async def prompt_generator_page(request: Request):
    return templates.TemplateResponse("prompt_generator.html", {"request": request})
"""@app.get("/download/{call_id}")
async def download_excel(call_id: str):
    filename = f"call_{call_id}.xlsx"
    if os.path.exists(filename):
        return FileResponse(filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=filename)
    return {"error": "File not found"}"""
# New route to list Excel files
@app.get("/files", response_class=HTMLResponse)
async def list_files(request: Request):
    excel_files = [f for f in os.listdir('.') if f.endswith('.xlsx')]
    return templates.TemplateResponse("file_list.html", {"request": request, "files": excel_files})

# New route to download files
@app.get("/download/{filename}")
async def download_file(filename: str):
    return FileResponse(filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=filename)

@app.post("/generate")
async def generate_prompt(message: Message):
    user_message = message.message
    if user_message.lower() == "generate prompt":
        response = prompt_generator(
            "Based on our discussion, please generate the comprehensive prompt for the caller agent.", "1")
    else:
        response = prompt_generator(user_message, "1")
    return {"response": response}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)