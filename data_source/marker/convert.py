def convert_single_pdf(input_path, model_lst, langs=["English"], batch_multiplier=2):
    print(f"[Stub] Converting {input_path} with models {model_lst}")
    
    # Simulated output
    full_text = "This is stubbed text from the PDF."
    images = []
    out_meta = {
        "input_path": input_path,
        "langs": langs,
        "batch_multiplier": batch_multiplier
    }

    return full_text, images, out_meta
