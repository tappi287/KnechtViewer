#! usr/bin/python_3

import re
from pathlib import Path
from typing import Union

import OpenImageIO as oiio
import numpy as np
from PySide2.QtGui import QPixmap, qRgb, QImage

from modules.utils.log import init_logging
from OpenImageIO import ImageBufAlgo, ImageSpec, ImageBuf, ImageOutput, geterror

LOGGER = init_logging(__name__)


def create_file_safe_name(filename: str) -> str:
    """ Replace any non alphanumeric characters from a string expect minus/underscore/period """
    return re.sub('[^\\w\\-_\\.]', '_', filename)


class OpenImageUtil:
    @classmethod
    def get_image_resolution(cls, img_file: Path) -> (int, int):
        img_input = cls._image_input(img_file)

        if img_input:
            res_x, res_y = img_input.spec().width, img_input.spec().height
            img_input.close()
            del img_input
            return res_x, res_y
        return 0, 0

    @staticmethod
    def get_last_error():
        return geterror()

    @classmethod
    def premultiply_image(cls, img_pixels: np.array) -> np.array:
        """ Premultiply a numpy image with itself """
        a = cls.np_to_imagebuf(img_pixels)
        ImageBufAlgo.premult(a, a)

        return a.get_pixels(a.spec().format, a.spec().roi_full)

    @staticmethod
    def get_numpy_oiio_img_format(np_array: np.ndarray):
        """ Returns either float or 8 bit integer format"""
        img_format = oiio.FLOAT
        if np_array.dtype != np.float32:
            img_format = oiio.UINT8

        return img_format

    @classmethod
    def np_to_imagebuf(cls, img_pixels: np.array):
        """ Load a numpy array 8/32bit to oiio ImageBuf """
        if len(img_pixels.shape) < 3:
            LOGGER.error('Can not create image with pixel data in this shape. Expecting 4 channels(RGBA).')
            return

        h, w, c = img_pixels.shape
        img_spec = ImageSpec(w, h, c, cls.get_numpy_oiio_img_format(img_pixels))

        img_buf = ImageBuf(img_spec)
        img_buf.set_pixels(img_spec.roi_full, img_pixels)

        return img_buf

    @classmethod
    def _image_input(cls, img_file: Path):
        """ CLOSE the returned object after usage! """
        img_input = oiio.ImageInput.open(img_file.as_posix())

        if img_input is None:
            LOGGER.error('Error reading image: %s', oiio.geterror())
            return
        return img_input

    @classmethod
    def read_image(cls, img_file: Path, img_format: str='') -> Union[np.ndarray, None]:
        """

        :param Path img_file: Path to the image file
        :param str img_format: string describing the format to -convert- to, see oiio docs, "float" is default
        :return:
        """
        img_input = cls._image_input(img_file)

        if not img_input:
            return None

        # Read out image data as numpy array
        img = img_input.read_image(format=img_format)
        img_input.close()

        return img

    @classmethod
    def read_img_metadata(cls, img_file: Path) -> dict:
        img_buf = ImageBuf(img_file.as_posix())
        img_dict = dict()

        if not img_buf:
            LOGGER.error(oiio.geterror())
            return img_dict

        for param in img_buf.spec().extra_attribs:
            img_dict[param.name] = param.value

        cls.close_img_buf(img_buf, img_file)

        return img_dict

    @classmethod
    def write_image(cls, file: Path, pixels: np.array):
        output = ImageOutput.create(file.as_posix())
        if not output:
            LOGGER.error('Error creating oiio image output:\n%s', oiio.geterror())
            return

        if len(pixels.shape) < 3:
            LOGGER.error('Can not create image with Pixel data in this shape. Expecting 3 or 4 channels(RGB, RGBA).')
            return

        h, w, c = pixels.shape
        spec = ImageSpec(w, h, c, cls.get_numpy_oiio_img_format(pixels))

        result = output.open(file.as_posix(), spec)
        if result:
            try:
                output.write_image(pixels)
            except Exception as e:
                LOGGER.error('Could not write Image: %s', e)
        else:
            LOGGER.error('Could not open image file for writing: %s: %s', file.name, output.geterror())

        output.close()

    @staticmethod
    def close_img_buf(img_buf, img_file: Union[Path, None]=None):
        try:
            img_buf.clear()
            del img_buf

            if img_file:
                oiio.ImageCache().invalidate(img_file.as_posix())
        except Exception as e:
            LOGGER.error('Error closing img buf: %s', e)


def read_to_qpixmap(image_path: Path) -> Union[str, QPixmap]:
    """ Read an image using OpenImageIO and return as QPixmap """
    img = OpenImageUtil.read_image(image_path)

    if img is None:
        return OpenImageUtil.get_last_error()

    if img.dtype != np.uint8:
        # Convert to integer and rescale to 0 - 255
        # original values should be float 0.0 - 1.0
        img = np.uint8(img * 255)

    return np_2_pixmap(img)


def np_2_pixmap(im: np.ndarray):
    """ Convert numpy array to QPixmap """

    qim = np_2_q_image(im)
    if qim is not None:
        return QPixmap.fromImage(qim)


gray_color_table = [qRgb(i, i, i) for i in range(256)]


def np_2_q_image(im: np.ndarray):
    """ Convert numpy array to QImage """
    if im.dtype == np.uint8:
        if len(im.shape) == 2:
            qim = QImage(im.data, im.shape[1], im.shape[0], im.strides[0], QImage.Format_Indexed8)
            qim.setColorTable(gray_color_table)
            return qim

        elif len(im.shape) == 3:
            if im.shape[2] == 3:
                qim = QImage(im.data, im.shape[1], im.shape[0], im.strides[0], QImage.Format_RGB888)
                return qim
            elif im.shape[2] == 4:
                qim = QImage(im.data, im.shape[1], im.shape[0], im.strides[0], QImage.Format_ARGB32)
                return qim
