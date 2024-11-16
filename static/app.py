from flask import Flask, render_template, request, jsonify, send_file
import cv2
import numpy as np
import os
from werkzeug.utils import secure_filename
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import io
from scipy.signal import savgol_filter

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/results', exist_ok=True)

# Global storage for all data
all_data = {
    'reference': None,
    'samples': {},
    'absorption': {},
    'filtered_absorption': {}  # New storage for filtered data
}

def apply_savgol_filter(data, window_length=15, polyorder=3):
    """Apply Savitzky-Golay filter to the data"""
    # Ensure window_length is odd and less than data length
    if window_length >= len(data):
        window_length = min(len(data) - 1 if len(data) % 2 == 0 else len(data) - 2, 15)
    if window_length % 2 == 0:
        window_length -= 1
    
    return savgol_filter(data, window_length, polyorder)

def get_rgb_profile_line(image, pointA, pointB):
    """Get RGB profile along a line between two points"""
    x0, y0 = pointA
    x1, y1 = pointB
    num_points = int(np.hypot(x1 - x0, y1 - y0))
    x_values = np.linspace(x0, x1, num_points).astype(int)
    y_values = np.linspace(y0, y1, num_points).astype(int)

    r_profile, g_profile, b_profile = [], [], []

    for x, y in zip(x_values, y_values):
        b, g, r = image[y, x]  # OpenCV loads images in BGR format
        b_profile.append(b)
        g_profile.append(g)
        r_profile.append(r)
    
    return np.array(r_profile), np.array(g_profile), np.array(b_profile)

def plot_rgb_profiles(r_profile, g_profile, b_profile, title, filename):
    """Create and save RGB profile plot"""
    plt.figure(figsize=(10, 6))
    x = np.arange(len(r_profile))
    
    plt.plot(x, r_profile, 'r-', label='Red', linewidth=2)
    plt.plot(x, g_profile, 'g-', label='Green', linewidth=2)
    plt.plot(x, b_profile, 'b-', label='Blue', linewidth=2)
    
    plt.title(title)
    plt.xlabel('Pixel Position')
    plt.ylabel('Intensity')
    plt.legend()
    plt.grid(True)
    
    plt.savefig(f'static/results/{filename}.png')
    plt.close()

def calculate_absorption(ref_r, ref_g, ref_b, sample_r, sample_g, sample_b):
    """Calculate absorption using the provided formula"""
    # Calculate I_reference and I_sample arrays element by element
    I_reference = np.zeros(len(ref_r))
    I_sample = np.zeros(len(sample_r))
    
    for i in range(len(ref_r)):
        # Calculate average for each pixel position
        I_reference[i] = (float(ref_r[i]) + float(ref_g[i]) + float(ref_b[i])) / 3.0
        I_sample[i] = (float(sample_r[i]) + float(sample_g[i]) + float(sample_b[i])) / 3.0
    
    # Avoid division by zero and log of zero
    I_reference = np.where(I_reference == 0, 0.000001, I_reference)
    I_sample = np.where(I_sample == 0, 0.000001, I_sample)
    
    absorption = -np.log10(I_sample / I_reference)
    return absorption, I_reference, I_sample

def plot_combined_absorption():
    """Create and save combined absorption plot with only filtered data"""
    plt.figure(figsize=(12, 6))
    
    # Plot reference line at zero
    x = np.arange(len(next(iter(all_data['absorption'].values()))))
    plt.plot(x, np.zeros_like(x), 'b-', label='Reference', linewidth=1)
    
    # Plot each filtered absorption profile
    colors = ['r', 'g', 'y', 'purple', 'orange']
    for i, (sample_id, _) in enumerate(all_data['absorption'].items()):
        color = colors[i % len(colors)]
        
        # Plot only filtered data
        filtered_data = all_data['filtered_absorption'][sample_id]
        plt.plot(x, filtered_data, color=color, linestyle='-',
                label=f'Sample {sample_id + 1}',
                linewidth=2)
    
    plt.title('Combined Absorption Profiles\n(Savitzky-Golay Filtered)')
    plt.xlabel('Pixel Position')
    plt.ylabel('Absorption')
    plt.legend()
    plt.grid(True)
    
    plt.savefig('static/results/combined_absorption_profile.png', dpi=300, bbox_inches='tight')
    plt.close()


def save_excel_data():
    """Save all data to Excel with proper organization, including filtered data"""
    if not all_data['reference'] or not all_data['samples']:
        return
    
    # Create a base dictionary with pixel positions
    num_points = len(all_data['reference']['red'])
    excel_data = {
        'Pixel_Position': np.arange(num_points)
    }
    
    # Add reference data
    excel_data.update({
        'I_Reference': all_data['reference']['intensity'],
        'Reference_Red': all_data['reference']['red'],
        'Reference_Green': all_data['reference']['green'],
        'Reference_Blue': all_data['reference']['blue']
    })
    
    # Add sample data, raw absorption, and filtered absorption for each sample
    for sample_id, sample_data in sorted(all_data['samples'].items()):
        prefix = f'Sample_{sample_id + 1}'
        excel_data.update({
            f'{prefix}_I_Sample': sample_data['intensity'],
            f'{prefix}_Red': sample_data['red'],
            f'{prefix}_Green': sample_data['green'],
            f'{prefix}_Blue': sample_data['blue'],
            f'{prefix}_Raw_Absorption': all_data['absorption'][sample_id],
            f'{prefix}_Filtered_Absorption': all_data['filtered_absorption'][sample_id]
        })
    
    # Create DataFrame and save to Excel
    df = pd.DataFrame(excel_data)
    df.to_excel('static/results/spectral_analysis_data.xlsx', index=False)
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'reference' not in request.files:
        return jsonify({'error': 'Missing reference file'}), 400
    
    reference = request.files['reference']
    samples = request.files.getlist('samples')
    
    if reference.filename == '' or not samples:
        return jsonify({'error': 'No selected files'}), 400
    
    # Clear previous data
    all_data['reference'] = None
    all_data['samples'].clear()
    all_data['absorption'].clear()
    
    # Save reference image
    ref_filename = 'ref.jpg'
    ref_path = os.path.join(app.config['UPLOAD_FOLDER'], ref_filename)
    reference.save(ref_path)
    
    # Save sample images
    sample_paths = []
    for i, sample in enumerate(samples):
        sample_filename = f'sample_{i}.jpg'
        sample_path = os.path.join(app.config['UPLOAD_FOLDER'], sample_filename)
        sample.save(sample_path)
        sample_paths.append(f'/static/uploads/{sample_filename}')
    
    return jsonify({
        'reference': f'/static/uploads/{ref_filename}',
        'samples': sample_paths
    })
@app.route('/analyze_line', methods=['POST'])
def analyze_line():
    try:
        data = request.get_json()
        pointA = (int(data['pointA']['x']), int(data['pointA']['y']))
        pointB = (int(data['pointB']['x']), int(data['pointB']['y']))
        sample_index = data.get('sampleIndex', 0)
        
        # Load reference image and specific sample image
        ref_image = cv2.imread(os.path.join(app.config['UPLOAD_FOLDER'], 'ref.jpg'))
        sample_image = cv2.imread(os.path.join(app.config['UPLOAD_FOLDER'], f'sample_{sample_index}.jpg'))
        
        if ref_image is None or sample_image is None:
            return jsonify({'error': 'Could not load images'}), 400
        
        # Get RGB profiles
        ref_r, ref_g, ref_b = get_rgb_profile_line(ref_image, pointA, pointB)
        sample_r, sample_g, sample_b = get_rgb_profile_line(sample_image, pointA, pointB)
        
        # Calculate absorption
        absorption, I_reference, I_sample = calculate_absorption(ref_r, ref_g, ref_b, sample_r, sample_g, sample_b)
        
        # Apply Savitzky-Golay filter to absorption data
        filtered_absorption = apply_savgol_filter(absorption)
        
        # Store reference data if not already stored
        if all_data['reference'] is None:
            all_data['reference'] = {
                'red': ref_r,
                'green': ref_g,
                'blue': ref_b,
                'intensity': I_reference
            }
        
        # Store sample data with sample index
        all_data['samples'][sample_index] = {
            'red': sample_r,
            'green': sample_g,
            'blue': sample_b,
            'intensity': I_sample
        }
        all_data['absorption'][sample_index] = absorption
        all_data['filtered_absorption'][sample_index] = filtered_absorption
        
        # Create profile plots
        plot_rgb_profiles(ref_r, ref_g, ref_b, 'RGB Profile Line - Reference', f'line_profile_reference_{sample_index}')
        plot_rgb_profiles(sample_r, sample_g, sample_b, f'RGB Profile Line - Sample {sample_index + 1}', f'line_profile_sample_{sample_index}')
        
        # Create combined absorption plot
        plot_combined_absorption()
        
        # Save all data to Excel
        save_excel_data()
        
        return jsonify({
            'reference_profile': f'/static/results/line_profile_reference_{sample_index}.png',
            'sample_profile': f'/static/results/line_profile_sample_{sample_index}.png',
            'absorption_profile': '/static/results/combined_absorption_profile.png'
        })
        
    except Exception as e:
        print("Error:", e)
        return jsonify({'error': str(e)}), 500
@app.route('/download_excel')
def download_excel():
    try:
        excel_path = 'static/results/spectral_analysis_data.xlsx'
        
        if not os.path.exists(excel_path):
            return jsonify({'error': 'No data available for download'}), 404
            
        return send_file(
            excel_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='spectral_analysis_data.xlsx'
        )
    except Exception as e:
        print("Download error:", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)