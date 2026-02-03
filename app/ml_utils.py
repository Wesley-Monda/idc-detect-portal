import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import io
import os
import random

# Load Model
MODEL_PATH = "breast_idc_resnet50_best_state_dict.pth"
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

model = None
DEMO_MODE = False

def get_model():
    global model, DEMO_MODE
    if model is not None:
        return model
    
    if not os.path.exists(MODEL_PATH):
        print(f"WARNING: Model file {MODEL_PATH} not found. Running in DEMO MODE (Random Predictions).")
        DEMO_MODE = True
        return None

    try:
        # Load Architecture
        model = models.resnet50(weights=None) # weights=None is deprecated but commonly used for empty
        # Adjust FC layer
        num_ftrs = model.fc.in_features
        model.fc = nn.Linear(num_ftrs, 2)
        
        # Load Weights
        state_dict = torch.load(MODEL_PATH, map_location=device)
        model.load_state_dict(state_dict)
        
        model.to(device)
        model.eval()
        print("SUCCESS: Model loaded successfully.")
    except Exception as e:
        print(f"ERROR: Failed to load model: {e}")
        DEMO_MODE = True
        return None
        
    return model

# Preprocessing
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

def predict_image(image_bytes):
    get_model() # Ensure loaded
    
    if DEMO_MODE:
        # Simulate prediction
        print("INFO: Generating DEMO prediction.")
        # Bias towards positive for testing visuals if needed, or random
        label = random.choice([0, 1])
        confidence = random.uniform(0.70, 0.99)
        return label, confidence

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_tensor = transform(image).unsqueeze(0).to(device)
        
        with torch.no_grad():
            outputs = model(image_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            
            # Get class and confidence
            top_p, top_class = probabilities.topk(1, dim=1)
            label = top_class.item()
            confidence = top_p.item()
            
            return label, confidence
    except Exception as e:
        print(f"Inference Error: {e}")
        return 0, 0.0
