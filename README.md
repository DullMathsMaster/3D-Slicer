# Raspberry-Pi based 3d printer

I started this project on a whim in 2023 after watching a video where someone printed a 3D printer using a 3D printer. However, this was only ever really a small project and I wanted it to be really budget friendly. And by REALLY budget friendly I meant EXTREMELY budget friendly. I picked up 4 stepper motors for about £10 total, skateboard bearings for £3 and a tonne of screws, nuts and bolts from BnQ (which as you can tell support the entire thing especially the raising platform) and began my mission.

At the time I had a Raspberry-Pi model 3b which is considered old now, however it still works and works well for this project. The project was simple and I thought it would be until I had my A-Levels and started university where it lay dormant until very recently. When I started my graphics module in university, it got me thinking about this project again and I decided to finish it.

## System architecture

I wanted to use a Raspberry Pi interface which I think is overkill for this system but it allows for modification to the sytem easily and perhaps for future usage

## Problems

The Pi did not have enough programmable pins. This was a problem if I wanted to have the stepper motors from the bottom to work with the system. My workaround was to use a Pi Pico directly interfaced with the pi to control the bottom stepper motors alone. This is pretty effective and worked well with the system as it only required 3 GPIO pins from the Pi 3: up, down and calibrate.

The system is shaky when moving up and down. This was anticipated by my younger self (well done me) and I did add extra holes for 2 more supports other than the BnQ bolts and nuts which rotate with the bottom 2 stepper motors.


## The Slicer

My original slicer uses OpensCad and an STL file system. This uses the bottom most vertices to create the layers of the 3D object into a series of black and white images to show each layer which is created by removing a fraction of a layer from the bottom each iteration using OpenSCAD command line interface.

After this, using the images as a reference, we can trace over the lines and create a path for the system to follow