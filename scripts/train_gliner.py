import os
import json
import torch
from pathlib import Path
from gliner import GLiNER
from gliner.data_processing.collator import SpanDataCollator

# If using gliner version 0.2+, the Trainer is available in gliner.training
try:
    from gliner.training import Trainer, TrainingArguments
except ImportError:
    print("Please install the latest gliner: pip install --upgrade gliner seqeval")
    exit(1)

DATASET_FILE = "NER_dataset/gliner_format.json"
MODEL_NAME = "urchade/gliner_medium-v2.1"
OUTPUT_DIR = "models/gliner-ikp-v1"

def load_dataset(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    print(f"Loading dataset from {DATASET_FILE}...")
    dataset = load_dataset(DATASET_FILE)
    print(f"Loaded {len(dataset)} training examples.")

    # In a real scenario, you'd split into train/eval. For this demo, we use all for train.
    train_dataset = dataset
    
    print(f"Loading base GLiNER model ({MODEL_NAME})...")
    model = GLiNER.from_pretrained(MODEL_NAME)
    
    # Check if GPU is available
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    model.to(device)

    print("Setting up training arguments...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        learning_rate=5e-6,
        weight_decay=0.01,
        others_lr=1e-5,
        others_weight_decay=0.01,
        lr_scheduler_type="linear",
        warmup_ratio=0.1,
        per_device_train_batch_size=4,
        num_train_epochs=5,
        save_steps=100,
        save_total_limit=1,
        dataloader_num_workers=0,
        use_cpu=(device.type == 'cpu')
    )

    data_collator = SpanDataCollator(model.config, data_processor=model.data_processor, prepare_labels=True)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=None,
        tokenizer=model.data_processor.transformer_tokenizer,
        data_collator=data_collator,
    )

    print("Starting Fine-tuning...")
    trainer.train()
    
    print(f"Training complete! Model saved to {OUTPUT_DIR}")
    
    # Save the model explicitly
    model.save_pretrained(OUTPUT_DIR)

if __name__ == "__main__":
    main()
