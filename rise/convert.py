"""One-time conversion: official Real-ESRGAN x4plus weights -> our pinned ONNX.

RRDBNet is inlined below (BSD-3-Clause, from xinntao/Real-ESRGAN — the
canonical 23-block generator) so conversion needs no basicsr install. Run:

    python -m rise.convert

Downloads the official .pth (64 MB), exports realesrgan-x4.onnx with dynamic
spatial axes into the control-z model store, prints the sha256 to pin.
"""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

PTH_URL = ("https://github.com/xinntao/Real-ESRGAN/releases/download/"
           "v0.1.0/RealESRGAN_x4plus.pth")


def _rrdbnet():
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    def make_layer(block, n, **kw):
        return nn.Sequential(*(block(**kw) for _ in range(n)))

    class ResidualDenseBlock(nn.Module):
        def __init__(self, num_feat=64, num_grow_ch=32):
            super().__init__()
            self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
            self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(0.2, True)

        def forward(self, x):
            import torch
            x1 = self.lrelu(self.conv1(x))
            x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
            x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
            x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
            x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
            return x5 * 0.2 + x

    class RRDB(nn.Module):
        def __init__(self, num_feat, num_grow_ch=32):
            super().__init__()
            self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
            self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
            self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

        def forward(self, x):
            return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x

    class RRDBNet(nn.Module):
        def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64,
                     num_block=23, num_grow_ch=32):
            super().__init__()
            self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
            self.body = make_layer(RRDB, num_block, num_feat=num_feat,
                                   num_grow_ch=num_grow_ch)
            self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(0.2, True)

        def forward(self, x):
            feat = self.conv_first(x)
            feat = feat + self.conv_body(self.body(feat))
            feat = self.lrelu(self.conv_up1(
                F.interpolate(feat, scale_factor=2, mode="nearest")))
            feat = self.lrelu(self.conv_up2(
                F.interpolate(feat, scale_factor=2, mode="nearest")))
            return self.conv_last(self.lrelu(self.conv_hr(feat)))

    return RRDBNet()


def main() -> int:
    import torch

    from czcore.models import models_dir

    dest_pth = models_dir() / "RealESRGAN_x4plus.pth"
    dest_onnx = models_dir() / "realesrgan-x4.onnx"
    if not dest_pth.exists():
        print(f"downloading official weights (BSD-3, xinntao): {PTH_URL}")
        urllib.request.urlretrieve(PTH_URL, dest_pth)
    net = _rrdbnet()
    state = torch.load(dest_pth, map_location="cpu", weights_only=True)
    net.load_state_dict(state["params_ema"])
    net.eval()
    dummy = torch.randn(1, 3, 64, 64)
    torch.onnx.export(
        net, (dummy,), str(dest_onnx), input_names=["input"], output_names=["output"],
        dynamic_axes={"input": {2: "h", 3: "w"}, "output": {2: "h", 3: "w"}},
        opset_version=17, dynamo=False,
    )
    sha = hashlib.sha256(dest_onnx.read_bytes()).hexdigest()
    print(f"exported {dest_onnx} ({dest_onnx.stat().st_size >> 20} MB)")
    print(f"sha256 {sha}")
    print("pin this in czcore.models REGISTRY['realesrgan-x4'] before release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
