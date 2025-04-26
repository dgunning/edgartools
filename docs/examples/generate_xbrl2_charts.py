#!/usr/bin/env python
"""
Generate visualizations for XBRL2 vs XBRL comparison analysis.

This script creates the charts and visualizations referenced in the
docs/xbrl2-rewrite-analysis.md file, showing comparisons between the 
original XBRL and the Claude-developed XBRL2 packages.
"""

import os
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import seaborn as sns
    VISUALIZATION_AVAILABLE = True
except ImportError:
    print("WARNING: Some visualization dependencies are missing.")
    print("To install required packages, run:")
    print("pip install matplotlib numpy pandas seaborn")
    VISUALIZATION_AVAILABLE = False

# Make sure output directory exists
image_dir = Path('../images')
if not image_dir.exists():
    image_dir.mkdir(parents=True)

# Set style for plots if visualization is available
if VISUALIZATION_AVAILABLE:
    sns.set(style="whitegrid")
    plt.rcParams['figure.figsize'] = (12, 8)
    plt.rcParams['font.size'] = 14

# Data for code metrics comparison
def create_code_metrics_chart():
    metrics = ['Lines of Code', 'Files', 'Classes', 'Functions', 'Docstrings']
    xbrl_values = [3466, 11, 29, 200, 101]
    xbrl2_values = [11289, 17, 104, 399, 644]
    
    # Create a DataFrame for cleaner plotting
    df = pd.DataFrame({
        'Metric': metrics,
        'XBRL': xbrl_values,
        'XBRL2': xbrl2_values
    })
    
    # Normalize the data for better visualization
    df_norm = df.copy()
    for col in ['XBRL', 'XBRL2']:
        df_norm[col] = df_norm[col] / df_norm[col].max()
    
    # Reshape for seaborn
    df_melted = pd.melt(df, id_vars=['Metric'], var_name='Package', value_name='Value')
    df_norm_melted = pd.melt(df_norm, id_vars=['Metric'], var_name='Package', value_name='Value')
    
    # First chart: Absolute values with log scale
    plt.figure(figsize=(14, 10))
    ax = sns.barplot(x='Metric', y='Value', hue='Package', data=df_melted)
    plt.yscale('log')
    plt.title('XBRL vs XBRL2 Code Metrics (log scale)', fontsize=20)
    plt.xlabel('Metric', fontsize=16)
    plt.ylabel('Count (log scale)', fontsize=16)
    
    # Add value labels on top of bars
    for i, p in enumerate(ax.patches):
        height = p.get_height()
        # Safer way to get the original value
        if i < len(df_melted):
            orig_value = df_melted.iloc[i]['Value']
            ax.text(p.get_x() + p.get_width()/2., height + 0.1,
                    f'{int(orig_value)}',
                    ha="center", fontsize=12)
    
    plt.tight_layout()
    plt.savefig(image_dir / 'xbrl2-code-metrics.png', dpi=300)
    plt.close()
    
    # Second chart: Code distribution
    # Data for file sizes
    xbrl_files = {
        '__init__.py': 28,
        'calculations.py': 98,
        'concepts.py': 148, 
        'definitions.py': 80,
        'dimensions.py': 121,
        'instance.py': 365,
        'labels.py': 87,
        'presentation.py': 474,
        'ratios.py': 0,
        'statements.py': 178,
        'xbrldata.py': 1887
    }
    
    xbrl2_files = {
        '__init__.py': 66,
        'analysis/': 1531,  # Sum of analysis module files
        'core.py': 331,
        'data/__init__.py': 5,
        'examples.py': 311,
        'facts.py': 1187,
        'models.py': 244,
        'parser.py': 1603,
        'periods.py': 491,
        'rendering.py': 1336,
        'standardization.py': 500,
        'statements.py': 772,
        'stitching.py': 1293,
        'transformers.py': 300,
        'xbrl.py': 1319
    }
    
    # Create subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 10))
    
    # XBRL plot
    wedges, texts, autotexts = ax1.pie(
        xbrl_files.values(), 
        labels=None,
        autopct='%1.1f%%', 
        startangle=90,
        pctdistance=0.85,
        wedgeprops={'edgecolor': 'w', 'linewidth': 1}
    )
    
    # Create legend with percentages
    total_xbrl = sum(xbrl_files.values())
    legend_labels = [f"{k} ({v} lines, {v/total_xbrl*100:.1f}%)" for k, v in xbrl_files.items()]
    ax1.legend(wedges, legend_labels, title="Files", loc="center left", bbox_to_anchor=(-0.1, 0))
    ax1.set_title('XBRL Package Code Distribution', fontsize=16)
    
    # XBRL2 plot
    wedges, texts, autotexts = ax2.pie(
        xbrl2_files.values(), 
        labels=None,
        autopct='%1.1f%%', 
        startangle=90,
        pctdistance=0.85,
        wedgeprops={'edgecolor': 'w', 'linewidth': 1}
    )
    
    # Create legend with percentages
    total_xbrl2 = sum(xbrl2_files.values())
    legend_labels = [f"{k} ({v} lines, {v/total_xbrl2*100:.1f}%)" for k, v in xbrl2_files.items()]
    ax2.legend(wedges, legend_labels, title="Files", loc="center right", bbox_to_anchor=(1.1, 0))
    ax2.set_title('XBRL2 Package Code Distribution', fontsize=16)
    
    plt.suptitle('Code Distribution Comparison', fontsize=20, y=1.05)
    plt.tight_layout()
    plt.savefig(image_dir / 'xbrl2-code-distribution.png', dpi=300, bbox_inches='tight')
    plt.close()

def create_api_functionality_chart():
    # Data for API functionality
    features = ['Input Flexibility', 'Rich Rendering', 'Data Export', 'Period Handling', 
                'Standardization', 'Analysis Tools', 'Cross-Company Comparison', 'Documentation']
    
    xbrl_scores = [2, 1, 1, 1, 0, 0, 0, 1]  # Scores out of 5
    xbrl2_scores = [4, 5, 5, 4, 5, 4, 4, 5]  # Scores out of 5
    
    # Create DataFrame
    df = pd.DataFrame({
        'Feature': features,
        'XBRL': xbrl_scores,
        'XBRL2': xbrl2_scores
    })
    
    # Reshape for radar chart
    categories = df['Feature'].tolist()
    
    # Set up the axes
    fig = plt.figure(figsize=(12, 10))
    ax = plt.subplot(111, polar=True)
    
    # Number of features
    N = len(categories)
    
    # Calculate angles for radar chart
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]  # Close the loop
    
    # Draw the chart for XBRL
    values = df['XBRL'].tolist()
    values += values[:1]  # Close the loop
    ax.plot(angles, values, 'b-', linewidth=2, label='XBRL')
    ax.fill(angles, values, 'b', alpha=0.1)
    
    # Draw the chart for XBRL2
    values = df['XBRL2'].tolist()
    values += values[:1]  # Close the loop
    ax.plot(angles, values, 'r-', linewidth=2, label='XBRL2')
    ax.fill(angles, values, 'r', alpha=0.1)
    
    # Set chart properties
    plt.xticks(angles[:-1], categories, size=12)
    plt.yticks([1, 2, 3, 4, 5], ['1', '2', '3', '4', '5'], color='grey', size=10)
    plt.ylim(0, 5)
    
    # Add legend
    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))
    
    # Add title
    plt.title('API Functionality Comparison', size=20, y=1.08)
    
    plt.tight_layout()
    plt.savefig(image_dir / 'xbrl2-api-functionality.png', dpi=300)
    plt.close()

def create_feature_comparison_chart():
    # Data for feature comparison
    features = ['Statement Rendering', 'Statement Stitching', 'Standardized Concepts', 'DataFrame Export',
                'Financial Ratios', 'Fraud Detection', 'Markdown Export', 'Period Handling']
    
    xbrl_has = [True, False, False, False, False, False, False, False]
    xbrl2_has = [True, True, True, True, True, True, True, True]
    
    # Create DataFrame
    df = pd.DataFrame({
        'Feature': features,
        'XBRL': xbrl_has,
        'XBRL2': xbrl2_has
    })
    
    # Reshape data for plotting
    df_melted = pd.melt(df, id_vars=['Feature'], var_name='Package', value_name='Supported')
    
    # Create plot
    plt.figure(figsize=(14, 8))
    ax = sns.barplot(
        data=df_melted,
        x="Feature", 
        y="Supported",
        hue="Package",
        palette=["#1f77b4", "#d62728"]
    )
    
    plt.title('Feature Comparison: XBRL vs XBRL2', fontsize=20, pad=20)
    plt.ylabel('Feature Supported', fontsize=16)
    plt.xlabel('Feature', fontsize=16)
    plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(image_dir / 'xbrl2-feature-comparison.png', dpi=300)
    plt.close()

def create_code_quality_chart():
    # Data for code quality metrics
    metrics = ['Documentation\nDensity', 'Test\nCoverage', 'Error\nHandling', 'Type\nAnnotations', 'Modern\nFeatures']
    xbrl_scores = [0.057, 0.3, 0.2, 0.3, 0.1]  # Normalized scores
    xbrl2_scores = [0.171, 0.7, 0.8, 0.9, 0.95]  # Normalized scores
    
    # Calculate 0-10 scores for visual impact
    xbrl_visual = [s * 10 for s in xbrl_scores]
    xbrl2_visual = [s * 10 for s in xbrl2_scores]
    
    # Create a dataframe
    df = pd.DataFrame({
        'Metric': metrics,
        'XBRL': xbrl_visual,
        'XBRL2': xbrl2_visual
    })
    
    # Reshape for seaborn
    df_melted = pd.melt(df, id_vars=['Metric'], var_name='Package', value_name='Score')
    
    # Create plot
    plt.figure(figsize=(14, 8))
    ax = sns.barplot(x='Metric', y='Score', hue='Package', data=df_melted, palette=["#1f77b4", "#d62728"])
    
    # Add value labels
    for i, p in enumerate(ax.patches):
        ax.annotate(f'{p.get_height():.1f}', 
                   (p.get_x() + p.get_width() / 2., p.get_height()), 
                   ha = 'center', va = 'bottom', 
                   xytext = (0, 5), textcoords = 'offset points')
    
    plt.title('Code Quality Metrics Comparison (0-10 scale)', fontsize=20)
    plt.xlabel('Metric', fontsize=16)
    plt.ylabel('Score', fontsize=16)
    plt.ylim(0, 10.5)  # Add space for labels
    
    plt.tight_layout()
    plt.savefig(image_dir / 'xbrl2-code-quality.png', dpi=300)
    plt.close()

def create_development_timeline_chart():
    """Create a chart showing the development timeline and code production for XBRL2."""
    # Development data from git logs
    dates = [
        "2025-03-09", "2025-03-10", "2025-03-12", "2025-03-13", "2025-03-14",
        "2025-03-15", "2025-03-17", "2025-03-18", "2025-03-19", "2025-03-20",
        "2025-03-21", "2025-03-22", "2025-03-25", "2025-03-26", "2025-03-27",
        "2025-03-28", "2025-03-29", "2025-03-30"
    ]
    
    commits = [2, 5, 1, 2, 4, 2, 2, 4, 1, 6, 7, 3, 5, 6, 2, 3, 1, 6]
    
    # Estimate lines of code per day (based on total LOC distributed proportionally)
    total_lines = 11289
    total_commits = sum(commits)
    estimated_lines = [int(c / total_commits * total_lines) for c in commits]
    
    # Create DataFrame
    df = pd.DataFrame({
        'Date': pd.to_datetime(dates),
        'Commits': commits,
        'Lines of Code': estimated_lines
    })
    
    # Sort by date
    df = df.sort_values('Date')
    
    # Create figure with dual y-axes
    fig, ax1 = plt.subplots(figsize=(14, 8))
    
    # Plot commits as bars
    ax1.bar(df['Date'], df['Commits'], color='#1f77b4', alpha=0.7, label='Commits')
    ax1.set_xlabel('Date', fontsize=14)
    ax1.set_ylabel('Number of Commits', fontsize=14, color='#1f77b4')
    ax1.tick_params(axis='y', labelcolor='#1f77b4')
    
    # Create second y-axis
    ax2 = ax1.twinx()
    
    # Plot lines of code as a line
    ax2.plot(df['Date'], df['Lines of Code'], color='#d62728', linewidth=2, marker='o', label='Lines of Code')
    ax2.set_ylabel('Estimated Lines of Code', fontsize=14, color='#d62728')
    ax2.tick_params(axis='y', labelcolor='#d62728')
    
    # Format x-axis to show dates nicely
    plt.xticks(rotation=45)
    fig.autofmt_xdate()
    
    # Add title
    plt.title('XBRL2 Development Timeline (March 9-30, 2025)', fontsize=18)
    
    # Add text with development stats
    avg_lines_per_day = total_lines / len(dates)
    ax1.text(0.02, 0.95, f"Total Lines: {total_lines}\nDevelopment Period: 21 days\nAvg: {avg_lines_per_day:.0f} lines/day",
             transform=ax1.transAxes, bbox=dict(facecolor='white', alpha=0.8))
    
    # Add combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    plt.tight_layout()
    plt.savefig(image_dir / 'xbrl2-development-timeline.png', dpi=300)
    plt.close()

def create_method_complexity_chart():
    """Create a chart showing method complexity metrics."""
    metrics = ['Methods', 'Avg Lines\nper Method', 'Max Line\nLength', 'if Statements\n(per 100 LOC)', 
              'for Loops\n(per 100 LOC)', 'elif Branches\n(per 100 LOC)']
    
    # Raw data
    xbrl_raw = [200, 17.3, 228, 333, 201, 30]
    xbrl2_raw = [272, 41.5, 157, 1590, 1250, 104]
    
    # Normalize per 100 lines of code for conditional statements
    xbrl_total_loc = 3466
    xbrl2_total_loc = 11289
    
    xbrl_values = [
        xbrl_raw[0],  # Methods
        xbrl_raw[1],  # Avg Lines per Method
        xbrl_raw[2],  # Max Line Length
        xbrl_raw[3] / xbrl_total_loc * 100,  # if Statements per 100 LOC
        xbrl_raw[4] / xbrl_total_loc * 100,  # for Loops per 100 LOC
        xbrl_raw[5] / xbrl_total_loc * 100,  # elif Branches per 100 LOC
    ]
    
    xbrl2_values = [
        xbrl2_raw[0],  # Methods
        xbrl2_raw[1],  # Avg Lines per Method
        xbrl2_raw[2],  # Max Line Length
        xbrl2_raw[3] / xbrl2_total_loc * 100,  # if Statements per 100 LOC
        xbrl2_raw[4] / xbrl2_total_loc * 100,  # for Loops per 100 LOC
        xbrl2_raw[5] / xbrl2_total_loc * 100,  # elif Branches per 100 LOC
    ]
    
    # Create DataFrame
    df = pd.DataFrame({
        'Metric': metrics,
        'XBRL': xbrl_values,
        'XBRL2': xbrl2_values
    })
    
    # Create a figure with multiple subplots
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()
    
    # Custom colors
    colors = ['#1f77b4', '#d62728']
    
    # Plot each metric in its own subplot
    for i, metric in enumerate(metrics):
        ax = axes[i]
        bars = ax.bar([0, 1], [df.loc[i, 'XBRL'], df.loc[i, 'XBRL2']], color=colors)
        ax.set_title(metric, fontsize=14)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(['XBRL', 'XBRL2'])
        
        # Add value labels
        if i < 3:  # For non-normalized metrics
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{height:.1f}', ha='center', fontsize=12)
        else:  # For normalized metrics
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{height:.2f}', ha='center', fontsize=12)
    
    # Add an overall title
    fig.suptitle('Method Complexity Comparison', fontsize=20)
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.9)
    plt.savefig(image_dir / 'xbrl2-method-complexity.png', dpi=300)
    plt.close()

def create_method_size_distribution():
    """Create a chart showing the distribution of method sizes."""
    # Estimated method size distributions
    xbrl_sizes = {
        '<20 lines': 65,
        '20-50 lines': 25,
        '>50 lines': 10
    }
    
    xbrl2_sizes = {
        '<20 lines': 48,
        '20-50 lines': 37,
        '>50 lines': 15
    }
    
    # Create DataFrame
    df = pd.DataFrame({
        'Size Range': list(xbrl_sizes.keys()),
        'XBRL': list(xbrl_sizes.values()),
        'XBRL2': list(xbrl2_sizes.values())
    })
    
    # Create plot
    plt.figure(figsize=(12, 8))
    
    # Position of bars on x-axis
    r1 = np.arange(len(df))
    r2 = [x + 0.3 for x in r1]
    
    # Create bars
    plt.bar(r1, df['XBRL'], color='#1f77b4', width=0.3, label='XBRL')
    plt.bar(r2, df['XBRL2'], color='#d62728', width=0.3, label='XBRL2')
    
    # Add labels and title
    plt.xlabel('Method Size Range', fontsize=14)
    plt.ylabel('Percentage of Methods (%)', fontsize=14)
    plt.title('Method Size Distribution', fontsize=18)
    plt.xticks([r + 0.15 for r in range(len(df))], df['Size Range'])
    
    # Add percentage labels on bars
    for i, v in enumerate(df['XBRL']):
        plt.text(i - 0.05, v + 1, f"{v}%", ha='center')
    
    for i, v in enumerate(df['XBRL2']):
        plt.text(i + 0.35, v + 1, f"{v}%", ha='center')
    
    # Add legend
    plt.legend()
    
    # Add text with additional statistics
    plt.text(0.02, 0.85, "XBRL Largest Method: 228 lines\nXBRL2 Largest Method: 157 lines",
             transform=plt.gca().transAxes, bbox=dict(facecolor='white', alpha=0.8), fontsize=12)
    
    plt.tight_layout()
    plt.savefig(image_dir / 'xbrl2-method-size.png', dpi=300)
    plt.close()

def create_architectural_complexity_chart():
    """Create a chart showing architectural complexity comparison."""
    # Define the complexity metrics
    metrics = [
        'Module Interdependence',
        'Inheritance Depth',
        'Interface Consistency',
        'Cohesion',
        'Coupling',
        'Separation of Concerns'
    ]
    
    # Scores are subjective ratings from 0-10
    # Higher score means better architecture in each metric
    xbrl_scores = [3, 2, 4, 5, 3, 4]
    xbrl2_scores = [7, 6, 8, 7, 8, 9]
    
    # Create DataFrame
    df = pd.DataFrame({
        'Metric': metrics,
        'XBRL': xbrl_scores,
        'XBRL2': xbrl2_scores
    })
    
    # Set up the axes for radar chart
    fig = plt.figure(figsize=(10, 10))
    ax = plt.subplot(111, polar=True)
    
    # Number of variables
    N = len(metrics)
    
    # Calculate angles for radar chart
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]  # Close the loop
    
    # Add labels around the chart
    plt.xticks(angles[:-1], metrics, size=12)
    
    # Draw y-axis labels (0-10)
    plt.yticks([2, 4, 6, 8, 10], ['2', '4', '6', '8', '10'], color='grey', size=10)
    plt.ylim(0, 10)
    
    # Plot XBRL data
    values = df['XBRL'].values.tolist()
    values += values[:1]  # Close the loop
    ax.plot(angles, values, 'b-', linewidth=2, label='XBRL')
    ax.fill(angles, values, 'b', alpha=0.1)
    
    # Plot XBRL2 data
    values = df['XBRL2'].values.tolist()
    values += values[:1]  # Close the loop
    ax.plot(angles, values, 'r-', linewidth=2, label='XBRL2')
    ax.fill(angles, values, 'r', alpha=0.1)
    
    # Add legend
    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))
    
    # Add title
    plt.title('Architectural Complexity Comparison', size=20, y=1.08)
    
    plt.tight_layout()
    plt.savefig(image_dir / 'xbrl2-architectural-complexity.png', dpi=300)
    plt.close()

if __name__ == "__main__":
    if not VISUALIZATION_AVAILABLE:
        print("ERROR: Required visualization packages are missing.")
        print("Please install the necessary packages:")
        print("pip install matplotlib numpy pandas seaborn")
        exit(1)
    
    print("Generating XBRL vs XBRL2 comparison charts...")
    
    try:
        # Create basic comparison charts
        create_code_metrics_chart()
        create_api_functionality_chart()
        create_feature_comparison_chart()
        create_code_quality_chart()
        
        # Create complexity analysis charts
        create_development_timeline_chart()
        create_method_complexity_chart()
        create_method_size_distribution()
        create_architectural_complexity_chart()
        
        print(f"Charts saved to {image_dir.absolute()}")
        print("Done!")
    except Exception as e:
        print(f"ERROR: Failed to generate charts: {e}")
        import traceback
        traceback.print_exc()
        exit(1)