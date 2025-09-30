import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import os
import json
from datetime import datetime

# -------- SETTINGS --------
CSV_FILE = "frame_counts.csv"
OUTPUT_DIR = "calibration_results"
SAVE_PLOTS = True
# --------------------------

def create_output_directory():
    """Create output directory for results"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

def load_and_validate_data():
    """Load and validate the input CSV file"""
    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(f"CSV file not found: {CSV_FILE}")
    
    try:
        df = pd.read_csv(CSV_FILE)
        
        # Validate required columns
        if "count" not in df.columns:
            raise ValueError("CSV file must contain a 'count' column")
        
        # Check for non-numeric count values
        if not pd.api.types.is_numeric_dtype(df["count"]):
            print("Warning: Converting 'count' column to numeric")
            df["count"] = pd.to_numeric(df["count"], errors='coerce')
            
        # Remove rows with invalid counts
        initial_rows = len(df)
        df = df.dropna(subset=["count"])
        df = df[df["count"] >= 0]  # Remove negative counts
        
        if len(df) < initial_rows:
            print(f"Removed {initial_rows - len(df)} rows with invalid count values")
        
        if len(df) == 0:
            raise ValueError("No valid data remaining after cleaning")
        
        print(f"Loaded {len(df)} valid samples from {CSV_FILE}")
        return df
        
    except Exception as e:
        raise Exception(f"Error loading CSV file: {e}")

def analyze_data_distribution(df):
    """Comprehensive analysis of data distribution"""
    counts = df["count"].values
    
    # Basic statistics
    stats_dict = {
        'count': len(counts),
        'mean': np.mean(counts),
        'median': np.median(counts),
        'std': np.std(counts),
        'min': np.min(counts),
        'max': np.max(counts),
        'q25': np.percentile(counts, 25),
        'q75': np.percentile(counts, 75),
        'iqr': np.percentile(counts, 75) - np.percentile(counts, 25)
    }
    
    print("\n=== Data Distribution Analysis ===")
    print(f"Sample count: {stats_dict['count']}")
    print(f"Mean: {stats_dict['mean']:.2f}")
    print(f"Median: {stats_dict['median']:.2f}")
    print(f"Standard deviation: {stats_dict['std']:.2f}")
    print(f"Range: {stats_dict['min']:.0f} - {stats_dict['max']:.0f}")
    print(f"IQR: {stats_dict['iqr']:.2f}")
    
    # Test for normality
    shapiro_stat, shapiro_p = stats.shapiro(counts)
    stats_dict['normality_test'] = {
        'shapiro_stat': float(shapiro_stat),
        'shapiro_p': float(shapiro_p),
        'is_normal': shapiro_p > 0.05
    }
    
    print(f"\nNormality test (Shapiro-Wilk):")
    print(f"  Statistic: {shapiro_stat:.4f}")
    print(f"  p-value: {shapiro_p:.4f}")
    print(f"  Distribution is {'normal' if shapiro_p > 0.05 else 'non-normal'}")
    
    return stats_dict

def analyze_labeled_data(df):
    """Analyze data with labels if available"""
    if "label" not in df.columns:
        print("No label column found - using percentile-based thresholds")
        return None
    
    print("\n=== Labeled Data Analysis ===")
    label_stats = df.groupby("label")["count"].describe()
    print(label_stats)
    
    # Statistical tests between groups
    labels = df["label"].unique()
    if len(labels) > 1:
        print("\n=== Group Comparison Tests ===")
        
        for i, label1 in enumerate(labels):
            for label2 in labels[i+1:]:
                group1 = df[df["label"] == label1]["count"]
                group2 = df[df["label"] == label2]["count"]
                
                # Mann-Whitney U test (non-parametric)
                u_stat, u_p = stats.mannwhitneyu(group1, group2, alternative='two-sided')
                print(f"{label1} vs {label2}:")
                print(f"  Mann-Whitney U: p = {u_p:.4f}")
                print(f"  Significant difference: {'Yes' if u_p < 0.05 else 'No'}")
    
    return label_stats

def calculate_thresholds(df, method='percentile'):
    """Calculate concentration thresholds using different methods"""
    counts = df["count"].values
    
    thresholds = {}
    
    if method == 'percentile':
        # Percentile-based thresholds
        low_thresh = np.percentile(counts, 33)
        med_thresh = np.percentile(counts, 66)
        thresholds['percentile'] = {
            'low': int(low_thresh),
            'medium': int(med_thresh),
            'method': 'percentile',
            'description': '33rd and 66th percentiles'
        }
    
    # Mean-based thresholds
    mean_val = np.mean(counts)
    std_val = np.std(counts)
    thresholds['mean_std'] = {
        'low': int(max(0, mean_val - std_val)),
        'medium': int(mean_val + std_val),
        'method': 'mean_std',
        'description': 'Mean ± 1 standard deviation'
    }
    
    # Median-based thresholds
    median_val = np.median(counts)
    q1 = np.percentile(counts, 25)
    q3 = np.percentile(counts, 75)
    thresholds['median_iqr'] = {
        'low': int(q1),
        'medium': int(q3),
        'method': 'median_iqr',
        'description': 'Q1 and Q3 (interquartile range)'
    }
    
    # If labeled data is available, use optimal thresholds
    if "label" in df.columns:
        optimal_thresholds = calculate_optimal_thresholds(df)
        if optimal_thresholds:
            thresholds['optimal'] = optimal_thresholds
    
    return thresholds

def calculate_optimal_thresholds(df):
    """Calculate optimal thresholds based on labeled data"""
    try:
        labels = sorted(df["label"].unique())
        
        if len(labels) != 3:
            print(f"Warning: Expected 3 concentration levels, found {len(labels)}")
            return None
        
        # Assuming labels are in order: Low, Medium, High
        low_data = df[df["label"] == labels[0]]["count"]
        med_data = df[df["label"] == labels[1]]["count"]
        high_data = df[df["label"] == labels[2]]["count"]
        
        # Find optimal thresholds to minimize misclassification
        # Use the midpoint between group medians as a starting point
        low_med = np.median(low_data)
        med_med = np.median(med_data)
        high_med = np.median(high_data)
        
        thresh1 = int((low_med + med_med) / 2)
        thresh2 = int((med_med + high_med) / 2)
        
        return {
            'low': thresh1,
            'medium': thresh2,
            'method': 'optimal',
            'description': f'Optimized based on labeled data ({labels})',
            'label_medians': {
                labels[0]: float(low_med),
                labels[1]: float(med_med),
                labels[2]: float(high_med)
            }
        }
        
    except Exception as e:
        print(f"Error calculating optimal thresholds: {e}")
        return None

def evaluate_thresholds(df, thresholds):
    """Evaluate threshold performance if labels are available"""
    if "label" not in df.columns:
        return None
    
    results = {}
    
    for method, thresh_data in thresholds.items():
        low_thresh = thresh_data['low']
        med_thresh = thresh_data['medium']
        
        # Apply thresholds
        predicted = []
        for count in df["count"]:
            if count <= low_thresh:
                predicted.append("Low")
            elif count <= med_thresh:
                predicted.append("Medium")
            else:
                predicted.append("High")
        
        # Calculate accuracy
        accuracy = sum(1 for true, pred in zip(df["label"], predicted) if true == pred) / len(df)
        
        results[method] = {
            'accuracy': accuracy,
            'thresholds': thresh_data
        }
        
        print(f"\n{method.upper()} method accuracy: {accuracy:.3f}")
    
    return results

def create_visualizations(df, thresholds, stats_dict):
    """Create comprehensive visualizations"""
    if not SAVE_PLOTS:
        return
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    
    # 1. Histogram with thresholds
    axes[0, 0].hist(df["count"], bins=30, alpha=0.7, color='skyblue', edgecolor='black')
    
    # Add threshold lines
    colors = ['red', 'orange', 'green', 'purple']
    for i, (method, thresh_data) in enumerate(thresholds.items()):
        if i >= len(colors):
            break
        axes[0, 0].axvline(thresh_data['low'], color=colors[i], linestyle='--', 
                          alpha=0.8, label=f"{method} Low")
        axes[0, 0].axvline(thresh_data['medium'], color=colors[i], linestyle='-', 
                          alpha=0.8, label=f"{method} Med")
    
    axes[0, 0].set_title('Count Distribution with Thresholds')
    axes[0, 0].set_xlabel('Particle Count')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # 2. Box plot
    if "label" in df.columns:
        sns.boxplot(data=df, x="label", y="count", ax=axes[0, 1])
        axes[0, 1].set_title('Count Distribution by Label')
    else:
        axes[0, 1].boxplot(df["count"])
        axes[0, 1].set_title('Count Box Plot')
        axes[0, 1].set_xticklabels(['All Data'])
    axes[0, 1].grid(True, alpha=0.3)
    
    # 3. Q-Q plot for normality
    stats.probplot(df["count"], dist="norm", plot=axes[0, 2])
    axes[0, 2].set_title('Q-Q Plot (Normality Check)')
    axes[0, 2].grid(True, alpha=0.3)
    
    # 4. Time series if filename suggests temporal order
    if "filename" in df.columns:
        try:
            # Try to extract frame numbers
            df['frame_num'] = df['filename'].str.extract(r'(\d+)').astype(int)
            df_sorted = df.sort_values('frame_num')
            axes[1, 0].plot(df_sorted['frame_num'], df_sorted['count'], alpha=0.7)
            axes[1, 0].set_title('Count Over Time (Frame Order)')
            axes[1, 0].set_xlabel('Frame Number')
            axes[1, 0].set_ylabel('Particle Count')
            axes[1, 0].grid(True, alpha=0.3)
        except:
            axes[1, 0].text(0.5, 0.5, 'Cannot extract\ntemporal order', 
                           ha='center', va='center', transform=axes[1, 0].transAxes)
    else:
        axes[1, 0].text(0.5, 0.5, 'No temporal\ninformation', 
                       ha='center', va='center', transform=axes[1, 0].transAxes)
    
    # 5. Cumulative distribution
    sorted_counts = np.sort(df["count"])
    y = np.arange(1, len(sorted_counts) + 1) / len(sorted_counts)
    axes[1, 1].plot(sorted_counts, y, linewidth=2)
    
    # Add percentile lines
    for percentile in [33, 66]:
        value = np.percentile(sorted_counts, percentile)
        axes[1, 1].axvline(value, color='red', linestyle='--', alpha=0.7)
        axes[1, 1].axhline(percentile/100, color='red', linestyle='--', alpha=0.7)
        axes[1, 1].text(value, percentile/100 + 0.05, f'{percentile}th', 
                       ha='center', color='red')
    
    axes[1, 1].set_title('Cumulative Distribution Function')
    axes[1, 1].set_xlabel('Particle Count')
    axes[1, 1].set_ylabel('Cumulative Probability')
    axes[1, 1].grid(True, alpha=0.3)
    
    # 6. Summary statistics
    axes[1, 2].axis('off')
    stats_text = f"""
    Sample Size: {stats_dict['count']}
    Mean: {stats_dict['mean']:.2f}
    Median: {stats_dict['median']:.2f}
    Std Dev: {stats_dict['std']:.2f}
    Min: {stats_dict['min']:.0f}
    Max: {stats_dict['max']:.0f}
    IQR: {stats_dict['iqr']:.2f}
    
    Normality Test:
    p-value: {stats_dict['normality_test']['shapiro_p']:.4f}
    Normal: {stats_dict['normality_test']['is_normal']}
    """
    axes[1, 2].text(0.1, 0.9, stats_text, transform=axes[1, 2].transAxes,
                    fontfamily='monospace', verticalalignment='top')
    
    plt.tight_layout()
    
    # Save plot
    plot_path = os.path.join(OUTPUT_DIR, 'calibration_analysis.png')
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    print(f"Visualizations saved to {plot_path}")
    plt.show()

def save_results(thresholds, stats_dict, evaluation_results=None):
    """Save all results to files"""
    
    # Prepare comprehensive results
    results = {
        'timestamp': datetime.now().isoformat(),
        'input_file': CSV_FILE,
        'statistics': stats_dict,
        'thresholds': thresholds,
        'evaluation': evaluation_results
    }
    
    # Save comprehensive results as JSON
    json_path = os.path.join(OUTPUT_DIR, 'calibration_results.json')
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save simple threshold file for backward compatibility
    recommended_method = 'optimal' if 'optimal' in thresholds else 'percentile'
    recommended_thresholds = thresholds[recommended_method]
    
    threshold_path = os.path.join(OUTPUT_DIR, 'concentration_thresholds.txt')
    with open(threshold_path, 'w') as f:
        f.write(f"{recommended_thresholds['low']},{recommended_thresholds['medium']}")
    
    # Save detailed report
    report_path = os.path.join(OUTPUT_DIR, 'calibration_report.txt')
    with open(report_path, 'w') as f:
        f.write("MICROPLASTIC CONCENTRATION CALIBRATION REPORT\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Input file: {CSV_FILE}\n\n")
        
        f.write("DATA STATISTICS:\n")
        f.write(f"  Sample count: {stats_dict['count']}\n")
        f.write(f"  Mean: {stats_dict['mean']:.2f}\n")
        f.write(f"  Median: {stats_dict['median']:.2f}\n")
        f.write(f"  Standard deviation: {stats_dict['std']:.2f}\n")
        f.write(f"  Range: {stats_dict['min']:.0f} - {stats_dict['max']:.0f}\n")
        f.write(f"  Distribution: {'Normal' if stats_dict['normality_test']['is_normal'] else 'Non-normal'}\n\n")
        
        f.write("THRESHOLD OPTIONS:\n")
        for method, thresh_data in thresholds.items():
            f.write(f"  {method.upper()}:\n")
            f.write(f"    Low ≤ {thresh_data['low']}\n")
            f.write(f"    Medium: {thresh_data['low']+1} - {thresh_data['medium']}\n")
            f.write(f"    High > {thresh_data['medium']}\n")
            f.write(f"    Method: {thresh_data['description']}\n")
            if evaluation_results and method in evaluation_results:
                f.write(f"    Accuracy: {evaluation_results[method]['accuracy']:.3f}\n")
            f.write("\n")
        
        f.write(f"RECOMMENDED: {recommended_method.upper()}\n")
        f.write(f"  Use thresholds: {recommended_thresholds['low']}, {recommended_thresholds['medium']}\n")
    
    print(f"\nResults saved:")
    print(f"  Comprehensive: {json_path}")
    print(f"  Simple thresholds: {threshold_path}")
    print(f"  Detailed report: {report_path}")
    
    return recommended_thresholds

def print_recommendations(thresholds, evaluation_results=None):
    """Print final recommendations"""
    print("\n" + "="*60)
    print("CALIBRATION RECOMMENDATIONS")
    print("="*60)
    
    # Choose best method
    if evaluation_results:
        best_method = max(evaluation_results.keys(), 
                         key=lambda x: evaluation_results[x]['accuracy'])
        print(f"BEST METHOD (highest accuracy): {best_method.upper()}")
        print(f"Accuracy: {evaluation_results[best_method]['accuracy']:.3f}")
    else:
        best_method = 'percentile'
        print(f"RECOMMENDED METHOD: {best_method.upper()} (no labels for validation)")
    
    best_thresholds = thresholds[best_method]
    
    print(f"\nRECOMMENDED THRESHOLDS:")
    print(f"  Low concentration: count ≤ {best_thresholds['low']}")
    print(f"  Medium concentration: {best_thresholds['low']+1} ≤ count ≤ {best_thresholds['medium']}")
    print(f"  High concentration: count > {best_thresholds['medium']}")
    
    print(f"\nCODE USAGE:")
    print(f"  CONC_THRESH = [{best_thresholds['low']}, {best_thresholds['medium']}]")
    
    if evaluation_results:
        print(f"\nALL METHOD ACCURACIES:")
        for method, results in evaluation_results.items():
            print(f"  {method}: {results['accuracy']:.3f}")
    
    print("\nNOTES:")
    print("  - Test these thresholds with your specific setup")
    print("  - Consider environmental factors (lighting, water clarity)")
    print("  - Recalibrate periodically for best results")
    print("="*60)

def main():
    """Main calibration pipeline"""
    print("=== Enhanced Microplastic Concentration Calibration ===")
    
    # Create output directory
    create_output_directory()
    
    # Load and validate data
    df = load_and_validate_data()
    
    # Analyze data distribution
    stats_dict = analyze_data_distribution(df)
    
    # Analyze labeled data if available
    label_stats = analyze_labeled_data(df)
    
    # Calculate thresholds using different methods
    thresholds = calculate_thresholds(df)
    
    # Evaluate thresholds if labels are available
    evaluation_results = evaluate_thresholds(df, thresholds)
    
    # Create visualizations
    create_visualizations(df, thresholds, stats_dict)
    
    # Save results
    recommended_thresholds = save_results(thresholds, stats_dict, evaluation_results)
    
    # Print recommendations
    print_recommendations(thresholds, evaluation_results)
    
    return recommended_thresholds

if __name__ == "__main__":
    try:
        recommended_thresholds = main()
    except Exception as e:
        print(f"Calibration failed: {e}")
        import traceback
        traceback.print_exc()