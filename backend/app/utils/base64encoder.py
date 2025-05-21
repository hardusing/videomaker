import base64


def encode_image(image_path):
    """
    read local image to encode it into base64 string
    """
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    return encoded_string
