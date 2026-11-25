# Importing all the tools we need to build our dashboard
# Like getting all the ingredients ready before cooking
import pandas as pd  # For working with data tables
import dash  # Main dashboard building tool
from dash import dcc, html, Input, Output, callback  # Parts for building the dashboard
import dash_bootstrap_components as dbc  # Makes our dashboard look pretty
import plotly.express as px  # For making charts
import plotly.graph_objects as go  # For special charts
from datetime import datetime  # For working with dates
import logging  # For keeping notes about what's happening

# Setting up a notebook to write down what happens while the dashboard runs
# Like keeping a diary for our program
logging.basicConfig(
    level=logging.INFO,  # Write down important things
    format="%(asctime)s - %(levelname)s - %(message)s",  # How to write each note
    handlers=[logging.StreamHandler()]  # Where to write the notes (on screen)
)
logger = logging.getLogger(__name__)  # Our notebook is ready to use

# Choosing colors for our dashboard
# Like picking crayons before drawing a picture
COLORS = {
    'background': '#0f0f13',  # Dark background color
    'text': '#ffffff',  # White text color
    'primary': '#ff4d88',  # Pink color for important things
    'secondary': '#00f2ff',  # Blue color for less important things
    'accent': '#ffcc00',  # Yellow color for special parts
    'card': '#1a1a2e',  # Color for information boxes
    'highlight': '#ff007f'  # Bright pink for attention
}

# Starting to build our dashboard
# Like opening a new art project
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])  # Using a dark theme
app.title = "DPDzero Call Analytics"  # Giving our dashboard a name

# This function loads and prepares our data
# Like sorting and organizing toys before playing with them
def load_and_process_data(call_logs_path='call_logs.csv', 
                         agent_roster_path='agent_roster.csv', 
                         disposition_path='disposition_summary.csv'):
    try:
        # Loading our three data files
        # Like opening three different books to read
        call_logs = pd.read_csv(call_logs_path, parse_dates=['call_date', 'created_ts'])  # Call records
        agent_roster = pd.read_csv(agent_roster_path)  # Agent information
        disposition = pd.read_csv(disposition_path, parse_dates=['call_date'])  # Agent login times
        
        # Checking if office location information exists
        # Like making sure all toys have their labels
        if 'users_office_location' not in agent_roster.columns:
            agent_roster['users_office_location'] = 'Unknown'  # Adding missing labels
            logger.warning("Added missing 'users_office_location' column with default values")
        
        # Combining call logs with agent information
        # Like matching puzzle pieces together
        merged = pd.merge(
            call_logs,
            agent_roster,
            on=["agent_id", "org_id"],  # Matching by agent and organization IDs
            how="left"  # Keep all call records even if agent info is missing
        )
        
        # Adding login time information to our combined data
        # Like adding another piece to our puzzle
        final_df = pd.merge(
            merged,
            disposition,
            on=["agent_id", "org_id", "call_date"],  # Matching by agent, org and date
            how="left"  # Keep all records even if login time is missing
        )
        
        # Calculating important numbers about each agent
        # Like counting how many goals each player scored
        metrics = final_df.groupby(["agent_id", "org_id", "call_date", "users_first_name", "users_last_name"]).agg(
            total_calls=("call_id", "count"),  # How many calls they made
            unique_loans=("installment_id", "nunique"),  # How many different loans they worked on
            completed_calls=("status", lambda x: (x == "completed").sum()),  # How many successful calls
            total_duration=("duration", "sum"),  # Total time spent on calls
            avg_duration=("duration", "mean"),  # Average call time
            presence=("login_time", lambda x: 0 if x.isna().all() else 1)  # Did they log in?
        ).reset_index()
        
        # Calculating success rate (percentage of completed calls)
        # Like calculating a test score percentage
        metrics["connect_rate"] = metrics["completed_calls"] / metrics["total_calls"]
        metrics["avg_duration"] = metrics["avg_duration"].round(2)  # Rounding to 2 decimal places
        metrics["agent_name"] = metrics["users_first_name"] + " " + metrics["users_last_name"]  # Full name
        
        # Adding office location to our metrics
        # Like adding address information to our report card
        if 'users_office_location' in final_df.columns:
            metrics = pd.merge(
                metrics,
                final_df[['agent_id', 'users_office_location']].drop_duplicates(),
                on='agent_id',
                how='left'
            )
        else:
            metrics['users_office_location'] = 'Unknown'
        
        logger.info("Data loaded and processed successfully")
        return metrics, final_df  # Returning both summary and detailed data
    
    except Exception as e:
        logger.error(f"Data processing failed: {e}")  # Writing down if something went wrong
        return pd.DataFrame(), pd.DataFrame()  # Returning empty tables if there's an error

# This function creates a simple text summary like a Slack message
# Like writing a short note about the day's performance
def generate_slack_summary(metrics_df, raw_df):
    """Generate a formatted Slack-style summary message"""
    report_date = metrics_df['call_date'].max().strftime('%Y-%m-%d')  # Getting the date
    
    # Finding the best performer (only among agents who logged in)
    active_agents = metrics_df[metrics_df['presence'] == 1]  # Only agents who were present
    top_performer = active_agents.loc[active_agents['connect_rate'].idxmax()]  # Best success rate
    top_name = f"{top_performer['users_first_name']} {top_performer['users_last_name']}"  # Their name
    top_rate = f"{top_performer['connect_rate']:.0%}"  # Their success percentage
    
    # Counting how many agents were active
    total_active_agents = active_agents['agent_id'].nunique()
    
    # Calculating average call time from all calls (not averaged averages)
    avg_duration = raw_df['duration'].mean()
    
    # Putting together our summary message
    slack_message = f"""
Agent Summary for {report_date}
-----------------------------
Top Performer: {top_name} ({top_rate} connect rate)
Total Active Agents: {total_active_agents}
Average Duration: {avg_duration:.1f} min
"""
    return slack_message

# Loading our prepared data
# Like getting our organized toys ready to play with
df, raw_df = load_and_process_data()
latest_date = df['call_date'].max().strftime('%Y-%m-%d')  # Finding the newest date

# Building the dashboard layout
# Like drawing where everything goes on our paper
app.layout = dbc.Container([
    # Big title at the top with download button
    # Like the heading of a poster
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("DPDZero CALL CENTER ANALYTICS DASHBOARD",  # Main title
                       className="display-4 mb-4",
                       style={'color': COLORS['primary']}),
                html.P(f"Latest Data: {latest_date}",  # Showing the date
                      className="lead",
                      style={'color': COLORS['secondary']}),
                dbc.Button(  # Download button
                    "Download Report as CSV",
                    id="download-btn",
                    color="primary",
                    className="mt-3",
                    style={'backgroundColor': COLORS['highlight']}
                ),
                dcc.Download(id="download-data")  # Hidden download helper
            ], className="text-center py-5")
        ], width=12)
    ]),
    
    # Four summary cards showing key numbers
    # Like scoreboards showing game stats
    dbc.Row([
        # Card 1: How many agents were active
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4("Total Active Agents", className="card-title"),
                html.H2(len(df[df['presence'] == 1]['agent_id'].unique()), 
                        id='agent-count',
                        style={'color': COLORS['primary']}),
            ])
        ], className="mb-4"), md=3),
        
        # Card 2: Total calls made
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4("Total Calls", className="card-title"),
                html.H2(df['total_calls'].sum(),
                        id='total-calls',
                        style={'color': COLORS['secondary']}),
            ])
        ], className="mb-4"), md=3),
        
        # Card 3: Average success rate
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4("Avg Connect Rate", className="card-title"),
                html.H2(f"{df['connect_rate'].mean()*100:.1f}%",
                        id='avg-connect-rate',
                        style={'color': COLORS['accent']}),
            ])
        ], className="mb-4"), md=3),
        
        # Card 4: Average call time
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4("Avg Call Duration", className="card-title"),
                html.H2(f"{raw_df['duration'].mean():.1f} min",
                        id='avg-duration',
                        style={'color': COLORS['highlight']}),
            ])
        ], className="mb-4"), md=3),
    ], className="mb-5"),
    
    # Slack-style summary box
    # Like a sticky note with key highlights
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Performance Summary"),
            dbc.CardBody([
                html.Pre(
                    id='slack-summary',
                    style={
                        'whiteSpace': 'pre-wrap',  # Keep our formatting
                        'fontFamily': 'monospace',  # Cool computer font
                        'color': COLORS['secondary'],
                        'backgroundColor': COLORS['card'],
                        'padding': '10px',
                        'borderRadius': '5px'
                    }
                )
            ])
        ], className="mb-4"), width=12)
    ]),
    
    # Date filter controls
    # Like a calendar to pick which days to look at
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("Filter by Date Range", className="card-title"),
                dcc.DatePickerRange(
                    id='date-range',
                    min_date_allowed=df['call_date'].min(),  # Earliest date available
                    max_date_allowed=df['call_date'].max(),  # Latest date available
                    start_date=df['call_date'].min(),  # Default start
                    end_date=df['call_date'].max()  # Default end
                )
            ])
        ], className="mb-4"), md=12),
    ]),
    
    # Charts section
    # Like pictures showing our data story
    dbc.Row([
        # Left chart: Top performers
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4("Top Performers", className="card-title"),
                dcc.Graph(id='top-performers')
            ])
        ], className="mb-4"), md=6),
        
        # Right chart: Performance scatter plot
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4("Performance Metrics", className="card-title"),
                dcc.Graph(id='performance-scatter')
            ])
        ], className="mb-4"), md=6),
    ]),
    
    # Data table at the bottom
    # Like a detailed report card
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4("Detailed Agent Data", className="card-title"),
                dcc.Graph(id='data-table')
            ])
        ], className="mb-4"), md=12),
    ])
], fluid=True, style={'backgroundColor': COLORS['background']})

# This makes the download button work
# Like connecting a button to a machine
@app.callback(
    Output("download-data", "data"),  # What comes out (the downloaded file)
    Input("download-btn", "n_clicks"),  # What starts it (button click)
    prevent_initial_call=True  # Don't download when page first loads
)
def download_data(n_clicks):
    # Preparing the data to download
    output_df = df[[
        'agent_id', 'org_id', 'call_date', 'users_first_name', 'users_last_name',
        'users_office_location', 'total_calls', 'unique_loans', 'completed_calls',
        'avg_duration', 'presence', 'connect_rate'
    ]]
    # Sending the CSV file to download
    return dcc.send_data_frame(output_df.to_csv, "agent_performance.csv", index=False)

# This makes everything update when we change dates
# Like refreshing the TV when we change channels
@app.callback(
    [Output('top-performers', 'figure'),  # Top performers chart
     Output('performance-scatter', 'figure'),  # Scatter plot
     Output('data-table', 'figure'),  # Data table
     Output('agent-count', 'children'),  # Active agents number
     Output('total-calls', 'children'),  # Total calls number
     Output('avg-connect-rate', 'children'),  # Success rate number
     Output('avg-duration', 'children'),  # Call duration number
     Output('slack-summary', 'children')],  # Slack message
    [Input('date-range', 'start_date'),  # When start date changes
     Input('date-range', 'end_date')]  # When end date changes
)
def update_dashboard(start_date, end_date):
    # Making copies of our data to filter
    filtered_df = df.copy()
    filtered_raw = raw_df.copy()
    
    # If dates are selected, filter our data
    if start_date and end_date:
        start_date = pd.to_datetime(start_date)  # Convert to proper date format
        end_date = pd.to_datetime(end_date)  # Convert to proper date format
        filtered_df = filtered_df[
            (filtered_df['call_date'] >= start_date) & 
            (filtered_df['call_date'] <= end_date)
        ]
        filtered_raw = filtered_raw[
            (filtered_raw['call_date'] >= start_date) & 
            (filtered_raw['call_date'] <= end_date)
        ]
    
    # Calculate our updated numbers
    active_agents = filtered_df[filtered_df['presence'] == 1]  # Only active agents
    agent_count = active_agents['agent_id'].nunique()  # Count unique agents
    total_calls = filtered_df['total_calls'].sum()  # Sum all calls
    avg_connect_rate = f"{filtered_df['connect_rate'].mean()*100:.1f}%"  # Average success
    avg_duration = f"{filtered_raw['duration'].mean():.1f}"  # Average call time
    
    # Generate the Slack message
    slack_summary = generate_slack_summary(filtered_df, filtered_raw)
    
    # Create the top performers bar chart
    top_performers = filtered_df.sort_values('connect_rate', ascending=False).head(10)
    top_fig = px.bar(
        top_performers,
        x='agent_name',  # Agent names on bottom
        y='connect_rate',  # Success rate on side
        color='connect_rate',  # Color by success rate
        title='Top Performers by Connect Rate',
        template='plotly_dark'  # Use dark theme
    )
    
    # Create the performance scatter plot
    scatter_fig = px.scatter(
        filtered_df,
        x='total_calls',  # Calls made on bottom
        y='connect_rate',  # Success rate on side
        color='users_office_location',  # Color by office
        size='avg_duration',  # Size by call time
        hover_name='agent_name',  # Show name when hovering
        title='Call Performance by Agent',
        template='plotly_dark'  # Use dark theme
    )
    
    # Create the data table
    table_fig = go.Figure(
        data=[go.Table(
            header=dict(
                values=['Agent', 'Calls', 'Connect Rate', 'Duration', 'Office'],  # Column names
                fill_color=COLORS['card'],  # Header color
                font=dict(color='white')  # White text
            ),
            cells=dict(
                values=[
                    filtered_df['agent_name'],  # Agent names
                    filtered_df['total_calls'],  # Call counts
                    filtered_df['connect_rate'].apply(lambda x: f"{x:.1%}"),  # Success %
                    filtered_df['avg_duration'].apply(lambda x: f"{x:.1f} min"),  # Call time
                    filtered_df['users_office_location']  # Office location
                ],
                fill_color=COLORS['background'],  # Cell color
                font=dict(color='white')  # White text
            )
        )]
    )
    
    # Return all our updated components
    return (top_fig, scatter_fig, table_fig, 
            agent_count, total_calls, avg_connect_rate, avg_duration,
            slack_summary)

# This starts our dashboard when we run the program
# Like pressing the "on" button
if __name__ == '__main__':
    app.run(debug=True)  # Run with extra error messages