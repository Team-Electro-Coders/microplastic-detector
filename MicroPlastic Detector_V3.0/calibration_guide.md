# ESP32 Microplastic Detector - Calibration Guide

## Why Calibration is Critical

Accurate scale calibration is the most important step for reliable microplastic detection. Without proper calibration, particle size measurements will be incorrect, leading to unreliable concentration estimates and unusable data.

## What is Scale Calibration?

The scale factor converts pixel measurements from the camera into real-world millimeter measurements. It answers the question: "How many millimeters does one pixel represent?"

**Formula:** `scale = actual_distance_mm / pixel_distance`

## Equipment Needed

- Your detection system setup (camera + sample area)
- Reference object with known dimensions:
  - **Recommended:** Precision ruler, calipers, or micrometer
  - **Acceptable:** Coin of known diameter, graph paper
  - **Best:** NIST-traceable calibration target

## Calibration Methods

### Method 1: Interactive Web Calibration (Recommended)

This is the easiest method using the web dashboard.

#### Steps:

1. **Prepare Reference Object**
   - Place a ruler or object of known size in the camera view
   - Ensure it's at the same focal plane as your samples
   - Good lighting is essential

2. **Access Calibration Tool**
   ```
   - Open web dashboard: http://localhost:5000
   - Click "Calibrate" button in video section
   - OR run: python main.py --calibrate
   ```

3. **Mark Reference Points**
   - Click two points spanning a known distance
   - Points should be clear and accurate
   - Example: Start and end of a 10mm ruler segment

4. **Enter Actual Distance**
   - Input the real distance between the two points in mm
   - Be as precise as possible (use decimal places)
   - Example: `10.0` mm for a 1cm ruler segment

5. **Confirm and Save**
   - System calculates scale factor automatically
   - Scale saved to `config.json`
   - Detector immediately uses new scale

#### Example:
```
Points clicked: (100, 200) to (500, 200)
Pixel distance: 400 pixels
Actual distance: 10.0 mm
Calculated scale: 0.025 mm/pixel
```

### Method 2: Manual Calculation

If you prefer to calculate manually:

#### Steps:

1. **Measure on Screen**
   - Capture a frame with reference object
   - Use image software to measure distance in pixels
   - Tools: GIMP, ImageJ, or online pixel rulers

2. **Calculate Scale**
   ```
   scale = actual_distance_mm / measured_pixels
   
   Example:
   Ruler shows 20mm
   Measures 800 pixels on screen
   scale = 20 / 800 = 0.025 mm/pixel
   ```

3. **Update Configuration**
   - Edit `config.json`:
     ```json
     {
       "detection": {
         "scale_mm_per_pixel": 0.025
       }
     }
     ```
   - Restart system to apply changes

### Method 3: Using Known Objects

Common reference objects with standard sizes:

#### Coins (approximate - verify with calipers):
- US Quarter: 24.26 mm diameter
- US Dime: 17.91 mm diameter
- US Penny: 19.05 mm diameter
- Euro €1: 23.25 mm diameter
- Euro €2: 25.75 mm diameter

#### Graph Paper:
- Standard: 5mm or 10mm squares
- Engineering: 0.1 inch (2.54mm) squares

#### Laboratory Items:
- Standard microscope slides: 75mm × 25mm
- Petri dishes: 90mm or 60mm diameter
- Pipette tips: verify with manufacturer specs

## Calibration Best Practices

### 1. Environmental Consistency
- **Same Setup:** Calibrate with exact same camera position and zoom
- **Same Lighting:** Use consistent illumination
- **Same Focus:** Don't change focus after calibration

### 2. Reference Object Placement
- **Correct Plane:** Place at same distance/depth as samples
- **Flat Surface:** Ensure object is perpendicular to camera
- **Center Frame:** Place near center to avoid lens distortion

### 3. Measurement Accuracy
- **Long Distance:** Use longest measurable distance for better accuracy
- **Multiple Points:** Take several measurements and average
- **Sharp Edges:** Select clear, well-defined reference points

### 4. Verification
- **Test Measurement:** Measure a different known object to verify
- **Expected Range:** Typical scales are 0.001 - 0.1 mm/pixel
- **Documentation:** Record calibration details (date, conditions, scale)

## Calibration Frequency

### When to Calibrate:

**Initial Setup:**
- Always calibrate when first setting up the system

**Regular Intervals:**
- Weekly for research-grade measurements
- Monthly for routine monitoring
- Before important experiments

**After Changes:**
- ✓ Camera moved or repositioned
- ✓ Lens zoom or focus adjusted
- ✓ Camera replaced or changed
- ✓ Sample chamber modified
- ✓ Lighting setup changed

## Troubleshooting Calibration Issues

### Problem: Wildly Incorrect Measurements

**Symptoms:** Particles showing as 10mm when they should be 0.1mm

**Solutions:**
- Check if scale is inverted (too large or too small by factor of 10)
- Verify units (make sure you entered mm, not cm or inches)
- Recalibrate with longer reference distance
- Check for decimal point errors

### Problem: Inconsistent Measurements

**Symptoms:** Similar particles showing very different sizes

**Solutions:**
- Check lighting consistency
- Verify camera is not auto-focusing
- Ensure sample is flat and in focus
- Check for lens distortion at frame edges
- Consider using smaller detection area (ROI)

### Problem: Calibration Changes After Restart

**Symptoms:** Scale resets to default value

**Solutions:**
- Verify `config.json` is being saved properly
- Check file permissions on config file
- Make sure you're running from correct directory
- Use absolute paths in configuration

## Advanced Calibration Techniques

### Multi-Point Calibration

For highest accuracy across entire frame:

1. Measure scale at multiple locations (center, edges, corners)
2. Average the measurements
3. Note any significant variations (indicates lens distortion)
4. Consider using smaller ROI if distortion is significant

```python
# Example multi-point calculation
measurements = [0.0248, 0.0251, 0.0247, 0.0249, 0.0250]
average_scale = sum(measurements) / len(measurements)
print(f"Average scale: {average_scale:.6f} mm/pixel")
print(f"Variation: ±{(max(measurements) - min(measurements))/2:.6f} mm/pixel")
```

### Microscope Calibration Standard

For highest precision:

1. Use stage micrometer (precision etched scale)
2. Typical: 1mm divided into 100 divisions (0.01mm each)
3. Measure multiple divisions
4. Calculate average scale factor

### Camera Matrix Calibration

For correcting lens distortion:

1. Use OpenCV calibration with checkerboard pattern
2. Calculate camera matrix and distortion coefficients
3. Apply undistortion before detection
4. Provides most accurate measurements

```python
# Example (requires camera calibration)
import cv2
import numpy as np

# Load calibration data
camera_matrix = np.load('camera_matrix.npy')
dist_coeffs = np.load('dist_coeffs.npy')

# Undistort frame
frame_undistorted = cv2.undistort(frame, camera_matrix, dist_coeffs)
```

## Validation and Quality Control

### Validation Checklist

After calibration, verify with these steps:

- [ ] Measure a different known object
- [ ] Size should be within ±5% of actual
- [ ] Test with multiple different sizes
- [ ] Document calibration parameters
- [ ] Check regularly with control samples

### Creating Control Samples

Prepare standard samples for regular verification:

1. **Microspheres:** Purchase calibrated microspheres (e.g., 100μm, 500μm)
2. **Test Particles:** Keep set of measured reference particles
3. **Regular Testing:** Measure control samples weekly
4. **Track Results:** Log measurements to detect drift

### Acceptance Criteria

**Good Calibration:**
- Measured sizes within ±5% of actual
- Consistent results across frame
- Repeatable measurements

**Needs Recalibration:**
- Measurements off by >10%
- Inconsistent across frame area
- Different from previous calibration by >20%

## Recording Calibration Data

### Calibration Log Template

```
Date: _______________
Operator: _______________
System: ESP32 Microplastic Detector

Reference Object: _______________
Actual Size: _______________ mm
Measured Pixels: _______________ px

Calculated Scale: _______________ mm/pixel

Test Object: _______________
Expected Size: _______________ mm
Measured Size: _______________ mm
Error: _______________ %

Notes:
_______________________________________
_______________________________________

Accepted: [ ] Yes  [ ] No
Signature: _______________
```

## Common Scale Factors

Typical scales for common setups:

- **USB Microscope (40-1000x):** 0.001 - 0.01 mm/pixel
- **Webcam (close-up):** 0.01 - 0.05 mm/pixel
- **IP Camera (macro):** 0.05 - 0.2 mm/pixel
- **DSLR Camera (macro lens):** 0.005 - 0.02 mm/pixel

## Additional Resources

- **ImageJ Calibration Guide:** https://imagej.nih.gov/ij/docs/guide/146-30.html
- **OpenCV Camera Calibration:** https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html
- **NIST Calibration Standards:** https://www.nist.gov/

## Support

If you encounter calibration issues:

1. Check this guide's troubleshooting section
2. Verify your hardware setup
3. Consult the main documentation
4. Report persistent issues to the development team

---

**Remember:** Good calibration is the foundation of accurate microplastic detection. Take your time and verify your results!