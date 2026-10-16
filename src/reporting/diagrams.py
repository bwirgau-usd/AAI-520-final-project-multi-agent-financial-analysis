"""Architecture diagrams and aggregate news charts for the final report."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from matplotlib import pyplot as plt
from matplotlib.figure import Figure


def plot_system_architecture(*, show: bool = True) -> Figure:
    """Render the implemented end-to-end research architecture."""

    figure, axes = plt.subplots(figsize=(14, 7))
    axes.set_title(
        "Multi-Agent Financial Analysis — System Architecture",
        fontsize=15,
        fontweight="bold",
        pad=18,
    )
    positions = {
        "Ticker": (0.06, 0.55),
        "Planner": (0.20, 0.55),
        "Market / SEC\nTools": (0.36, 0.74),
        "News\nPrompt Chain": (0.36, 0.35),
        "Specialist\nRouter": (0.53, 0.35),
        "Evaluator /\nOptimizer": (0.68, 0.35),
        "Synthesizer": (0.68, 0.74),
        "Final Report\n+ Visuals": (0.84, 0.55),
        "Memory": (0.84, 0.18),
    }
    edges = (
        ("Ticker", "Planner"),
        ("Planner", "Market / SEC\nTools"),
        ("Planner", "News\nPrompt Chain"),
        ("News\nPrompt Chain", "Specialist\nRouter"),
        ("Specialist\nRouter", "Evaluator /\nOptimizer"),
        ("Market / SEC\nTools", "Synthesizer"),
        ("Evaluator /\nOptimizer", "Synthesizer"),
        ("Synthesizer", "Final Report\n+ Visuals"),
        ("Final Report\n+ Visuals", "Memory"),
        ("Memory", "Planner"),
    )
    _draw_flow(axes, positions, edges)
    if show:
        plt.show()
    return figure


def plot_news_workflow(*, show: bool = True) -> Figure:
    """Render prompt chaining, routing, and evaluator–optimizer flow."""

    figure, axes = plt.subplots(figsize=(15, 5.5))
    axes.set_title(
        "Financial News Workflow",
        fontsize=15,
        fontweight="bold",
        pad=18,
    )
    positions = {
        "Yahoo + NewsAPI\n+ Google RSS": (0.06, 0.67),
        "Preprocess": (0.19, 0.67),
        "Classify": (0.32, 0.67),
        "Extract": (0.45, 0.67),
        "Summarize": (0.58, 0.67),
        "Route": (0.71, 0.67),
        "Specialist": (0.84, 0.67),
        "Evaluate": (0.71, 0.25),
        "Optimize": (0.84, 0.25),
        "Report": (0.95, 0.46),
    }
    edges = (
        ("Yahoo + NewsAPI\n+ Google RSS", "Preprocess"),
        ("Preprocess", "Classify"),
        ("Classify", "Extract"),
        ("Extract", "Summarize"),
        ("Summarize", "Route"),
        ("Route", "Specialist"),
        ("Specialist", "Evaluate"),
        ("Evaluate", "Optimize"),
        ("Optimize", "Evaluate"),
        ("Evaluate", "Report"),
    )
    _draw_flow(axes, positions, edges, node_width=0.105)
    axes.text(
        0.775,
        0.08,
        "Revision loop stops at the quality threshold or iteration limit",
        ha="center",
        fontsize=9,
        color="#374151",
    )
    if show:
        plt.show()
    return figure


def plot_news_analysis_summary(
    news_analysis: Mapping[str, Any],
    *,
    show: bool = True,
) -> Figure | None:
    """Plot source coverage, routing distribution, and evaluator scores."""

    articles = news_analysis.get("articles")
    if not isinstance(articles, list) or not articles:
        return None

    source_counts = _numeric_mapping(news_analysis.get("source_counts"))
    routing_counts = _numeric_mapping(news_analysis.get("routing_counts"))
    scores = []
    labels = []
    for index, raw_article in enumerate(articles, start=1):
        article = raw_article if isinstance(raw_article, Mapping) else {}
        evaluation = article.get("evaluation")
        evaluation = evaluation if isinstance(evaluation, Mapping) else {}
        score = evaluation.get("score")
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            scores.append(float(score))
            labels.append(str(index))

    figure, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    _bar_chart(axes[0], source_counts, "Articles by Source", "Articles")
    _bar_chart(axes[1], routing_counts, "Specialist Routing", "Articles")
    axes[2].bar(labels, scores, color="#7c3aed")
    threshold = news_analysis.get("evaluation_threshold")
    if isinstance(threshold, (int, float)) and not isinstance(threshold, bool):
        axes[2].axhline(
            float(threshold),
            color="#dc2626",
            linestyle="--",
            linewidth=1.5,
            label=f"Threshold ({float(threshold):g})",
        )
        axes[2].legend(loc="lower right")
    axes[2].set_title("Final Evaluation Scores")
    axes[2].set_xlabel("Article")
    axes[2].set_ylabel("Score / 100")
    axes[2].set_ylim(0, 105)
    axes[2].grid(axis="y", alpha=0.2)
    figure.suptitle(
        f"{news_analysis.get('ticker', 'Company')} News Analysis Summary",
        fontsize=15,
        fontweight="bold",
    )
    figure.tight_layout()
    if show:
        plt.show()
    return figure


def _draw_flow(
    axes: Any,
    positions: Mapping[str, tuple[float, float]],
    edges: Sequence[tuple[str, str]],
    *,
    node_width: float = 0.12,
) -> None:
    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)
    axes.axis("off")
    for start, end in edges:
        start_x, start_y = positions[start]
        end_x, end_y = positions[end]
        axes.annotate(
            "",
            xy=(end_x, end_y),
            xytext=(start_x, start_y),
            arrowprops={
                "arrowstyle": "->",
                "color": "#475569",
                "linewidth": 1.5,
                "shrinkA": 26,
                "shrinkB": 26,
                "connectionstyle": "arc3,rad=0.05",
            },
            zorder=1,
        )
    for label, (x, y) in positions.items():
        axes.text(
            x,
            y,
            label,
            ha="center",
            va="center",
            fontsize=9.5,
            fontweight="bold",
            bbox={
                "boxstyle": "round,pad=0.55",
                "facecolor": "#dbeafe",
                "edgecolor": "#2563eb",
                "linewidth": 1.4,
            },
            zorder=2,
        )
    axes.margins(x=node_width)


def _numeric_mapping(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): float(item)
        for key, item in value.items()
        if isinstance(item, (int, float)) and not isinstance(item, bool)
    }


def _bar_chart(axes: Any, values: Mapping[str, float], title: str, ylabel: str) -> None:
    labels = list(values) or ["None"]
    heights = list(values.values()) or [0]
    axes.bar(labels, heights, color="#2563eb")
    axes.set_title(title)
    axes.set_ylabel(ylabel)
    axes.tick_params(axis="x", rotation=20)
    axes.grid(axis="y", alpha=0.2)
