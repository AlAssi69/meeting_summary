from __future__ import annotations

import gc


def collect_and_empty_torch_cuda_cache() -> None:
    """Run GC and release PyTorch CUDA allocator cache when CUDA is available."""
    gc.collect()
    try:
        import torch
    except ImportError:
        return
    if not torch.cuda.is_available():
        return
    try:
        torch.cuda.synchronize()
    except Exception:
        pass
    torch.cuda.empty_cache()
