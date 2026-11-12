"""PixelOE 1.0.0 torch adapter; CPU only, oracle target size, quantization off."""

from . import _common as common

INSTALL = (
    "Install pixeloe==1.0.0 yourself after reviewing OpenCV/PyTorch and bundled dependency "
    "licenses. CyberSprite does not declare this tree as an extra or download model weights."
)


def available():
    return common.available("pixeloe.torch.pixelize", INSTALL)


def describe():
    return common.describe("pixeloe", "pixeloe", "Apache-2.0")


def run(rgba, params):
    frames, _ = common.inputs(rgba, params, ("target_w", "target_h", "pixel_size", "thickness"))
    width = common.positive(params, "target_w", maximum=frames[0].shape[1])
    height = common.positive(params, "target_h", maximum=frames[0].shape[0])
    size = common.positive(params, "pixel_size", 4, maximum=16)
    thickness = params.get("thickness", 2)
    if type(thickness) is not int or not 0 <= thickness <= 8:
        raise common.invalid("PixelOE thickness must be an integer from 0 to 8.")
    module = common.load("pixeloe.torch.pixelize", INSTALL)
    torch = common.load("torch", INSTALL)
    functional = common.load("torch.nn.functional", INSTALL)
    with common.LOCK:
        threads = torch.get_num_threads()
        deterministic = torch.are_deterministic_algorithms_enabled()
        warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
        try:
            torch.set_num_threads(1)
            torch.use_deterministic_algorithms(True)
            with torch.random.fork_rng(devices=[]):
                torch.random.default_generator.manual_seed(0)
                with torch.no_grad():
                    tensor = torch.from_numpy(frames[0]).permute(2, 0, 1).unsqueeze(0).float() / 255
                    tensor = functional.interpolate(
                        tensor, size=(height * size, width * size), mode="nearest"
                    )
                    pixels = module.pixelize(
                        tensor[:, :3],
                        pixel_size=size,
                        thickness=thickness,
                        do_quant=False,
                        do_color_match=False,
                        no_post_upscale=True,
                        backend="torch",
                    )
                    alpha = functional.interpolate(
                        tensor[:, 3:4], size=(height, width), mode="nearest"
                    )
                    result = torch.cat((pixels, alpha), dim=1).clamp(0, 1).mul(255).round()
                    result = result[0].permute(1, 2, 0).to(torch.uint8).cpu().numpy()
        finally:
            torch.set_num_threads(threads)
            torch.use_deterministic_algorithms(deterministic, warn_only=warn_only)
    return common.output(result), {
        **describe(),
        "device": "cpu",
        "threads": 1,
        "seed": 0,
        "oracle_size": True,
        "target_size": [width, height],
        "quantized": False,
        "pre_resize": "nearest to target_size * pixel_size",
        "alpha": "nearest from input",
    }
