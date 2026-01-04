import google.generativeai as genai
import os

genai.configure(api_key="AIzaSyBfeS8ZMzGyNHktgl9ZYOWs8Nz6mJCTjPQ")

print("รายชื่อโมเดลที่บัญชีนี้ใช้ได้:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"- {m.name}")