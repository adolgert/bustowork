#!/bin/bash
# Run sequential heat map generation
# Can be run in screen/tmux for long-running analysis

echo "Starting sequential heat map generation..."
echo "This will take several hours - consider running in screen/tmux"
echo ""

python src/grid_generator.py

echo ""
echo "Heat map generation complete!"
echo "Results saved to heatmap_data.json"
