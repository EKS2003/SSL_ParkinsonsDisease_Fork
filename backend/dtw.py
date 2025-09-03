import sys
import json
import numpy as np
import matplotlib.pyplot as plt
from dtaidistance import dtw
import pandas as pd

def load_motion_data(file_path):
    """Load motion data from a JSON file."""
    with open(file_path, "r") as f:
        data = json.load(f)
    
    return np.array(data["frames"]), np.array(data["nose_x"]), np.array(data["nose_y"])

def compare_motion_data(file1, file2):
    """Load, compare, and visualize motion data from two JSON files using DTW."""
    
    # Load both datasets
    frames1, nose_x1, nose_y1 = load_motion_data(file1)
    frames2, nose_x2, nose_y2 = load_motion_data(file2)

    # Calculate DTW distance and best path for X motion
    distance_x, paths_x = dtw.warping_paths(nose_x1, nose_x2, use_c=False)
    best_path_x = dtw.best_path(paths_x)

    # Calculate DTW distance and best path for Y motion
    distance_y, paths_y = dtw.warping_paths(nose_y1, nose_y2, use_c=False)
    best_path_y = dtw.best_path(paths_y)

    similarity_score_x = distance_x / len(best_path_x)
    similarity_score_y = distance_y / len(best_path_y)

    plt.figure(figsize=(12, 14))  # Increase figure size for better visibility

    ### X-MOTION PLOTS ###
    
    # Original Time Series - X Motion
    ax1 = plt.subplot2grid((4, 2), (0, 0))
    ax1.plot(nose_x1, label='Nose X - Series 1', color='blue', marker='o', linestyle='-')
    ax1.plot(nose_x2, label='Nose X - Series 2', linestyle='--', color='orange', marker='x')
    ax1.set_title('Original Time Series - X Motion')
    ax1.legend()
    ax1.grid(True)

    # Shortest Path - X Motion
    ax2 = plt.subplot2grid((4, 2), (0, 1))
    ax2.plot(np.array(best_path_x)[:, 0], np.array(best_path_x)[:, 1], 'green', marker='o', linestyle='-')
    ax2.set_title('Shortest Path - X Motion')
    ax2.set_xlabel('Series 1')
    ax2.set_ylabel('Series 2')
    ax2.grid(True)

    # Point-to-Point Comparison - X Motion
    ax3 = plt.subplot2grid((4, 2), (1, 0), colspan=2)
    ax3.plot(nose_x1, label='Nose X - Series 1', color='blue', marker='o')
    ax3.plot(nose_x2, label='Nose X - Series 2', color='orange', marker='x', linestyle='--')
    for a, b in best_path_x:
        ax3.plot([a, b], [nose_x1[a], nose_x2[b]], color='grey', linestyle='-', linewidth=1, alpha=0.5)
    ax3.set_title('Point-to-Point Comparison After DTW Alignment - X Motion')
    ax3.legend()
    ax3.grid(True)

    ### Y-MOTION PLOTS ###

    # Original Time Series - Y Motion
    ax4 = plt.subplot2grid((4, 2), (2, 0))
    ax4.plot(nose_y1, label='Nose Y - Series 1', color='blue', marker='o', linestyle='-')
    ax4.plot(nose_y2, label='Nose Y - Series 2', linestyle='--', color='orange', marker='x')
    ax4.set_title('Original Time Series - Y Motion')
    ax4.legend()
    ax4.grid(True)

    # Shortest Path - Y Motion
    ax5 = plt.subplot2grid((4, 2), (2, 1))
    ax5.plot(np.array(best_path_y)[:, 0], np.array(best_path_y)[:, 1], 'green', marker='o', linestyle='-')
    ax5.set_title('Shortest Path - Y Motion')
    ax5.set_xlabel('Series 1')
    ax5.set_ylabel('Series 2')
    ax5.grid(True)

    # Point-to-Point Comparison - Y Motion
    ax6 = plt.subplot2grid((4, 2), (3, 0), colspan=2)  # Fixed from (3,2) to (4,2)
    ax6.plot(nose_y1, label='Nose Y - Series 1', color='blue', marker='o')
    ax6.plot(nose_y2, label='Nose Y - Series 2', color='orange', marker='x', linestyle='--')
    for a, b in best_path_y:
        ax6.plot([a, b], [nose_y1[a], nose_y2[b]], color='grey', linestyle='-', linewidth=1, alpha=0.5)
    ax6.set_title('Point-to-Point Comparison After DTW Alignment - Y Motion')
    ax6.legend()
    ax6.grid(True)

    plt.tight_layout()
    plt.show()

    # Display similarity scores
    results_df = pd.DataFrame({
        'Metric': ['DTW Similarity Score (X)', 'DTW Similarity Score (Y)'],
        'Value': [similarity_score_x, similarity_score_y]
    })

    results_df['Description'] = [
        "Lower scores indicate greater similarity in X motion.",
        "Lower scores indicate greater similarity in Y motion."
    ]

    print(results_df)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python compare_motion_dtw.py <file1.json> <file2.json>")
        sys.exit(1)

    file1 = sys.argv[1]
    file2 = sys.argv[2]

    compare_motion_data(file1, file2)
