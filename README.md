# KOL Insight - Twitter KOL Evaluation System

A comprehensive Twitter KOL (Key Opinion Leader) evaluation system that automatically crawls Twitter data, performs AI-powered scoring analysis, and generates evaluation reports.

**中文文档**: [README_cn.md](README_cn.md)

## Features

- ✅ **Automatic Twitter Data Crawling** - Fetches user information and tweets via TweetScout API
- ✅ **AI-Powered Scoring Analysis** - Multi-dimensional scoring using GPT API (Originality, Content Depth, Human Vitality, etc.)
- ✅ **Normalization Parameter Management** - Unified normalization parameters ensure comparable results
- ✅ **Static HTML Report Generation** - Automatically generates beautiful static HTML evaluation reports
- ✅ **Web Interface** - User-friendly web interface for easy access

## Quick Start

### Method 1: Using Web Interface (Recommended)

1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

2. **Set API Keys**
```bash
# Linux/macOS
export TWEETSCOUT_API_KEY="your-tweetscout-key"
export OPENAI_API_KEY="your-openai-key"

# Windows PowerShell
$env:TWEETSCOUT_API_KEY="your-tweetscout-key"
$env:OPENAI_API_KEY="your-openai-key"

# Windows CMD
set TWEETSCOUT_API_KEY=your-tweetscout-key
set OPENAI_API_KEY=your-openai-key
```

3. **Start Web Service**
```bash
python app.py
```

4. **Access Web Interface**
Open your browser and visit `http://localhost:5000`, enter a Twitter username to automatically generate an evaluation report.

### Method 2: Using Command Line

1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

2. **Set API Keys** (same as above)

3. **Modify Username**

Edit `generate_report.py`, modify the username on line 27:

```python
USERNAME = "elonmusk"  # Change to the username you want to analyze
```

4. **Run Program**
```bash
python generate_report.py
```

5. **View Results**

After the program completes, open `static_html/index.html` or `static_html/user_0.html` to view the evaluation report.

## Project Structure

```
KOL-Insight/
├── app.py                      # Web service (Flask application)
├── generate_report.py          # Main program (integrates all features)
├── twitter_crawler.py          # Twitter crawler module
├── generate_static_html.py     # HTML generator
├── update_normalization.py     # Normalization parameter update script
├── requirements.txt            # Dependencies
│
├── scoring/                    # Scoring engine
│   ├── engine.py               # Score calculation engine
│   ├── schema.py               # Scoring rules definition
│   └── normalization_manager.py # Normalization parameter management
│
├── models/                     # Data models
│   ├── data_model.py           # Account and Tweet models
│   └── score_node.py           # Score node structure
│
├── views/                      # HTML templates
│   ├── view_scores.html        # Main page template
│   └── user_report.html        # User report template
│
├── templates/                  # Flask templates
│   └── index.html              # Web interface template
│
├── utils.py                    # Utility functions (GPT API calls)
│
├── data/                       # Data directory
│   └── twitter_data_*.db       # Crawled raw data (SQLite databases)
│
├── outputs/                    # Output directory
│   ├── normalization_params.json  # Normalization parameters
│   ├── raw_scores_history.json    # Historical raw scores
│   ├── accounts_*.json            # Account data
│   ├── tweets_*.json              # Tweet data
│   ├── scores_*.json              # Score data
│   └── tree_structure_*.json      # Score tree structure
│
└── static_html/                # Generated HTML pages
    ├── index_*.html            # Main pages
    └── user_*.html             # User detailed reports
```

## Configuration

You can modify the following configurations in `generate_report.py` or `app.py`:

```python
# Twitter username to analyze (without @)
USERNAME = "elonmusk"

# Crawling configuration
MAX_TWEETS = 50          # Maximum tweets to crawl per user
SKIP_COMMENTS = True     # Whether to skip comments (True speeds up crawling)

# Scoring configuration
TWEETS_LIMIT = 10        # Only use top N tweets for scoring (prevents excessive AI API calls)
```

## Scoring Dimensions

The system evaluates KOLs from 6 dimensions:

1. **Originality** - Evaluates the originality of content
2. **Human Vitality** - Detects bot activity, fake followers, etc.
3. **KOL Influence** - Evaluates recognition within the KOL community
4. **Content Depth** - Evaluates the depth and quality of tweet content
5. **Engagement** - Evaluates audience interaction with content
6. **Views** - Evaluates content reach

**Final Score** = (Average of other 5 factors) × Human Vitality

## Normalization Parameter Management

### Using Existing Normalization Parameters

The system automatically loads normalization parameters from `outputs/normalization_params.json`. If the file doesn't exist, it will calculate using the current batch data.

### Updating Normalization Parameters

After accumulating enough historical data, you can run:

```bash
python update_normalization.py
```

This will recalculate min/max values based on all historical raw scores and update the normalization parameters.

### Raw Score History

Each time `generate_report.py` runs, the system automatically:
- Saves raw scores to `outputs/raw_scores_history.json`
- Uses existing normalization parameters for normalization

## Workflow

```
Input Username (USERNAME)
    ↓
[Step 1] Crawl Twitter Data
    → Use twitter_crawler.py
    → Generate data/twitter_data_*.db
    ↓
[Step 2] Convert Data Format
    → Adapt database structure
    → Convert to Account/Tweet objects
    ↓
[Step 3] Calculate Scores
    → Load normalization parameters
    → Use AI to analyze tweets
    → Calculate 6-dimensional scores
    → Save raw scores to history
    → Generate outputs/scores_*.json
    ↓
[Step 4] Generate Evaluation Pages
    → Generate static HTML files
    → Save to static_html/
    ↓
Output Evaluation Pages ✅
```

## API Key Setup

### TweetScout API

1. Visit [TweetScout.io](https://tweetscout.io/)
2. Register an account and choose a suitable subscription plan
3. Get your API key from the API settings

### OpenAI API

1. Visit [OpenAI API Platform](https://platform.openai.com/api-keys)
2. Log in or register an account
3. Click "Create new secret key"
4. Copy the generated key

## Important Notes

1. **API Costs**: The scoring feature requires OpenAI API calls, which incur costs. It's recommended to test with `TWEETS_LIMIT = 5` first.
2. **Crawling Speed**: Crawling comments significantly increases time and API calls. It's recommended to set `SKIP_COMMENTS = True`.
3. **Data Limits**: To avoid excessive API consumption, only the top 10 tweets are used for scoring by default.
4. **Normalization Parameters**: On first run without normalization parameters, the system will calculate using current batch data, which may make results from different batches incomparable.

## Troubleshooting

### 1. API Key Error

```
❌ Error: TWEETSCOUT_API_KEY environment variable not set
```

**Solution**: Ensure environment variables are set correctly.

### 2. User Not Found

```
❌ Failed to crawl tweets for xxx
```

**Solution**:
- Check if the username is correct (without @)
- Confirm the user exists and is accessible
- Check if TweetScout API is working properly

### 3. Scoring Failed

```
❌ Score calculation failed
```

**Solution**:
- Check if OpenAI API key is correct
- Check if account balance is sufficient
- Reduce the value of `TWEETS_LIMIT`

## Technical Details

### Score Calculation Process

1. **Leaf Node Raw Score Calculation**: Calculate raw scores for all leaf nodes for each account
2. **Leaf Node Normalization**: Use existing normalization parameters (or current batch data) for min-max normalization
3. **Non-Leaf Node Calculation**: Use weighted average to calculate parent node scores
4. **Root Node Calculation**: Use multiplication rule: `Total Score = other_factors × human_vitality`

### Normalization Mechanism

- **Leaf Node Normalization**: Use min-max normalization to map raw scores to 0-1 range
- **Normalization Parameters**: Saved in `outputs/normalization_params.json`
- **Historical Data**: Raw scores from each calculation are automatically saved to `outputs/raw_scores_history.json`

### AI Features

- **Human Vitality**: Uses GPT API to analyze bot activity
- **Content Depth**: Uses GPT API to evaluate content depth
- **Root Comment**: Uses GPT API to generate comprehensive account comments

These features incur API costs.

### Asynchronous Computation

The scoring engine supports asynchronous concurrent computation to improve efficiency. Leaf node score calculation and AI comment generation are executed concurrently.

## Modifying Scoring Rules

To modify scoring rules, edit the scoring tree structure in `scoring/schema.py`, then run `generate_report.py` to recalculate scores.

You can modify:
- Add/delete/modify leaf nodes
- Adjust weights
- Modify normalization settings (`normalize` attribute)
- Modify scoring functions (`calc_raw`)
- Adjust tree structure (add intermediate nodes)
- Modify root node calculation rules (currently multiplication rule)

**Important**: The `outputs/tree_structure_*.json` file is automatically generated from `schema.py`. Do not modify this file directly.

## License

This project follows the license of the original project.
