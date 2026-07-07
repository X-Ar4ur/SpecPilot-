import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { inflateSync } from "node:zlib";
import test from "node:test";

function readPng(path) {
  const data = readFileSync(path);
  const signature = data.subarray(0, 8).toString("hex");
  assert.equal(signature, "89504e470d0a1a0a");

  let width = 0;
  let height = 0;
  let colorType = 0;
  const idat = [];

  for (let offset = 8; offset < data.length; ) {
    const length = data.readUInt32BE(offset);
    const type = data.subarray(offset + 4, offset + 8).toString("ascii");
    const chunk = data.subarray(offset + 8, offset + 8 + length);

    if (type === "IHDR") {
      width = chunk.readUInt32BE(0);
      height = chunk.readUInt32BE(4);
      assert.equal(chunk[8], 8);
      colorType = chunk[9];
      assert.ok(colorType === 2 || colorType === 6);
    } else if (type === "IDAT") {
      idat.push(chunk);
    } else if (type === "IEND") {
      break;
    }

    offset += 12 + length;
  }

  const channels = colorType === 6 ? 4 : 3;
  const bytesPerPixel = channels;
  const stride = width * bytesPerPixel;
  const raw = inflateSync(Buffer.concat(idat));
  const pixels = Buffer.alloc(width * height * bytesPerPixel);

  for (let y = 0; y < height; y += 1) {
    const srcRow = y * (stride + 1);
    const dstRow = y * stride;
    const filter = raw[srcRow];

    for (let x = 0; x < stride; x += 1) {
      const left = x >= bytesPerPixel ? pixels[dstRow + x - bytesPerPixel] : 0;
      const up = y > 0 ? pixels[dstRow + x - stride] : 0;
      const upLeft =
        y > 0 && x >= bytesPerPixel
          ? pixels[dstRow + x - stride - bytesPerPixel]
          : 0;
      const value = raw[srcRow + 1 + x];

      if (filter === 0) {
        pixels[dstRow + x] = value;
      } else if (filter === 1) {
        pixels[dstRow + x] = (value + left) & 255;
      } else if (filter === 2) {
        pixels[dstRow + x] = (value + up) & 255;
      } else if (filter === 3) {
        pixels[dstRow + x] = (value + Math.floor((left + up) / 2)) & 255;
      } else if (filter === 4) {
        const p = left + up - upLeft;
        const pa = Math.abs(p - left);
        const pb = Math.abs(p - up);
        const pc = Math.abs(p - upLeft);
        const predictor = pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft;
        pixels[dstRow + x] = (value + predictor) & 255;
      } else {
        throw new Error(`Unsupported PNG filter: ${filter}`);
      }
    }
  }

  return { width, height, channels, pixels };
}

test("logo image has a pure white background", () => {
  const png = readPng(new URL("../../image/logo.png", import.meta.url));
  const samplePoints = [
    [0, 0],
    [Math.floor(png.width / 2), 0],
    [png.width - 1, 0],
    [0, Math.floor(png.height / 2)],
    [png.width - 1, Math.floor(png.height / 2)],
    [0, png.height - 1],
    [Math.floor(png.width / 2), png.height - 1],
    [png.width - 1, png.height - 1],
  ];

  for (const [x, y] of samplePoints) {
    const offset = (y * png.width + x) * png.channels;
    assert.deepEqual(
      [...png.pixels.subarray(offset, offset + 3)],
      [255, 255, 255],
      `background pixel ${x},${y} should be white`,
    );
  }
});
