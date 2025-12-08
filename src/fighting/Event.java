package fighting;

import java.util.ArrayList;
import image.Image;
import manager.GraphicManager;



public class Event {
    protected LoopAnimation loopAnimation;
    protected int x, y;
    protected int vx, vy;
    protected int duration;
    protected int hitX, hitY;
    protected int eventId;
    protected int eventType;
    protected float scale;

    public Event(int eventId , int eventType) {
        this.eventId = eventId;
        this.eventType = eventType;
        this.scale = 0.5f;
        
        // Hardcode values
        this.x = 400;
        this.y = 300;
        this.vx = 0;
        this.vy = 0;
        this.duration = 60;
        this.hitX = 0;
        this.hitY = 0;
        
        // Get images
        ArrayList<ArrayList<Image>> eventImages = GraphicManager.getInstance().getEventImageContainer();
        Image[] images = new Image[0];
        if (eventImages != null && eventImages.size() > eventType && eventImages.get(eventType) != null) {
             ArrayList<Image> list = eventImages.get(eventType);
             images = list.toArray(new Image[0]);
        }

        this.loopAnimation = new LoopAnimation(images);
    }

    public boolean update() {
        this.duration--;
        if (this.duration <= 0) {
            return false;
        }
        
        this.x += this.vx;
        this.y += this.vy;
        
        this.loopAnimation.update();
        
        return true;
    }

    public Image getImage() {
        return this.loopAnimation.getImage();
    }
    
    public int getX() {
        return x;
    }

    public int getY() {
        return y;
    }

    public int getEventId() {
        return eventId;
    }

    public int getVx() {
        return vx;
    }

    public int getVy() {
        return vy;
    }
    public int getDuration() {
        return duration;
    }
    
    public float getScale() {
        return scale;
    }
    
    public void setScale(float scale) {
        this.scale = scale;
    }

    public void initialize(int x, int y, int vx, int vy, int duration, int hitX, int hitY) {
        this.x = x;
        this.y = y;
        this.vx = vx;
        this.vy = vy;
        this.duration = duration;
        this.hitX = hitX;
        this.hitY = hitY;
    }
}
