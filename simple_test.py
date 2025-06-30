#!/usr/bin/env python3
import os
print("Python is working!")
print("Azure key loaded:", bool(os.getenv('AZURE_OPENAI_API_KEY')))
print("Done.") 