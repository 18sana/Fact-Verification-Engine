"""QLoRA fine-tuning for the Skeptic student model."""

import json
from pathlib import Path
from typing import Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def run_qlora_finetuning(
    training_jsonl_path: str,
    output_dir: str,
    settings: Optional[Settings] = None,
) -> dict:
    """
    Fine-tune student model with LoRA on exported training JSONL.
    Requires: torch, transformers, peft, datasets
    """
    settings = settings or get_settings()
    path = Path(training_jsonl_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        return {"status": "error", "message": f"Training file not found: {path}"}

    records = []
    with open(path) as f:
        for line in f:
            records.append(json.loads(line))
    if not records:
        return {"status": "error", "message": "No training records"}

    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
        from transformers import Trainer, DataCollatorForLanguageModeling
    except ImportError as e:
        return {
            "status": "error",
            "message": f"Install peft, transformers, datasets, bitsandbytes for training: {e}",
        }

    def format_example(rec: dict) -> str:
        return (
            f"### Instruction:\n{rec['instruction']}\n\n"
            f"### Input:\n{rec['input']}\n\n"
            f"### Response:\n{rec['output']}"
        )

    texts = [format_example(r) for r in records]
    dataset = Dataset.from_dict({"text": texts})

    tokenizer = AutoTokenizer.from_pretrained(settings.student_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    use_cuda = torch.cuda.is_available()
    quant_config = None
    if use_cuda:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )

    model = AutoModelForCausalLM.from_pretrained(
        settings.student_model,
        quantization_config=quant_config,
        device_map="auto" if use_cuda else None,
        torch_dtype=torch.float16 if use_cuda else torch.float32,
    )

    if use_cuda:
        model = prepare_model_for_kbit_training(model)

    # Pick LoRA targets that exist on the loaded architecture (Phi, GPT-2, etc.)
    preferred = ["q_proj", "v_proj", "k_proj", "o_proj", "c_attn", "c_proj", "c_fc"]
    module_names = {name.split(".")[-1] for name, _ in model.named_modules()}
    target_modules = [m for m in preferred if m in module_names]
    if not target_modules:
        target_modules = ["c_attn", "c_proj"]

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
    )
    model = get_peft_model(model, lora_config)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=512, padding="max_length")

    tokenized = dataset.map(tokenize, batched=True, remove_columns=["text"])

    training_args = TrainingArguments(
        output_dir=str(out / "checkpoints"),
        num_train_epochs=1 if not use_cuda else 3,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=10,
        save_steps=50,
        save_total_limit=2,
        fp16=use_cuda,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    logger.info("finetuning_started", samples=len(records), output=str(out))
    trainer.train()

    adapter_path = out
    model.save_pretrained(str(adapter_path))
    tokenizer.save_pretrained(str(adapter_path))

    return {
        "status": "completed",
        "output_dir": str(adapter_path),
        "samples_trained": len(records),
        "student_model": settings.student_model,
        "method": "qlora" if use_cuda else "lora_cpu",
    }
