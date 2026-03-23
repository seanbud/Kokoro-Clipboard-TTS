const sharp = require('sharp');

async function scaleIcon() {
  try {
    await sharp('C:/Users/Sean/Downloads/sheba_yell.png')
      .resize(1024, 1024, {
        kernel: sharp.kernel.nearest
      })
      .toFile('public/icon.png');
    console.log('Successfully scaled icon to 1024x1024 using nearest-neighbor interpolation.');
  } catch (err) {
    console.error('Error scaling icon:', err);
    process.exit(1);
  }
}

scaleIcon();
