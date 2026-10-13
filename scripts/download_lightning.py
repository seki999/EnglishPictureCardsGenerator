"""Download ByteDance's official four-step SDXL Lightning LoRA."""
import download_sdxl as downloader

downloader.TARGET = downloader.ROOT / '.runtime/ComfyUI/models/loras/sdxl_lightning_4step_lora.safetensors'
downloader.URL = 'https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_4step_lora.safetensors'
downloader.SIZE = 393854592
downloader.SHA256 = 'bf56cf2657efb15e465d81402ed481d1e11c4677e4bcce1bc11fe71ad8506b79'

if __name__ == '__main__':
    downloader.main()
