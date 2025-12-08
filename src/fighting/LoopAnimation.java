package fighting;

import image.Image;

public class LoopAnimation {
    private Image[] images;
    private int currentFrame;
    private int framesPerImage;

    public LoopAnimation(Image[] images) {
        this(images, 1);
    }

    public LoopAnimation(Image[] images, int framesPerImage) {
        this.images = images;
        this.framesPerImage = framesPerImage;
        this.currentFrame = 0;
    }

    public void update() {
        this.currentFrame++;
    }

    public Image getImage() {
        if (this.images == null || this.images.length == 0) {
            return null;
        }
        int index = (this.currentFrame / this.framesPerImage) % this.images.length;
        return this.images[index];
    }
}
