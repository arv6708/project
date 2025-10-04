import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import sqlite3
import json
import calendar

# Page configuration
st.set_page_config(
    page_title="Period Tracker",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #ff69b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #ff69b4;
        margin: 0.5rem 0;
    }
    .prediction-card {
        background-color: #fff0f5;
        padding: 1.5rem;
        border-radius: 10px;
        border: 2px solid #ff69b4;
        margin: 1rem 0;
    }
    .section-header {
        color: #ff69b4;
        border-bottom: 2px solid #ff69b4;
        padding-bottom: 0.5rem;
        margin: 2rem 0 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Database functions
def init_db():
    conn = sqlite3.connect('period_tracker.db')
    c = conn.cursor()
    
    # Create cycles table
    c.execute('''
        CREATE TABLE IF NOT EXISTS cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            cycle_length INTEGER,
            period_length INTEGER,
            symptoms TEXT,
            mood TEXT,
            flow_level TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect('period_tracker.db', check_same_thread=False)

# PeriodTracker class
class PeriodTracker:
    def __init__(self):
        self.conn = get_connection()
    
    def add_cycle(self, start_date, end_date, symptoms=None, mood=None, flow_level=None, notes=None):
        cycle_length = None
        period_length = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days + 1
        
        # Calculate cycle length if we have previous cycles
        previous_cycle = self.get_previous_cycle(start_date)
        if previous_cycle:
            prev_start = datetime.strptime(previous_cycle[1], '%Y-%m-%d')
            current_start = datetime.strptime(start_date, '%Y-%m-%d')
            cycle_length = (current_start - prev_start).days
        
        c = self.conn.cursor()
        c.execute('''
            INSERT INTO cycles (start_date, end_date, cycle_length, period_length, symptoms, mood, flow_level, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (start_date, end_date, cycle_length, period_length, 
              json.dumps(symptoms) if symptoms else None, 
              mood, flow_level, notes))
        self.conn.commit()
        return c.lastrowid
    
    def get_cycles(self, limit=50):
        c = self.conn.cursor()
        c.execute('SELECT * FROM cycles ORDER BY start_date DESC LIMIT ?', (limit,))
        return c.fetchall()
    
    def get_previous_cycle(self, current_start_date):
        c = self.conn.cursor()
        c.execute('''
            SELECT * FROM cycles 
            WHERE start_date < ? 
            ORDER BY start_date DESC 
            LIMIT 1
        ''', (current_start_date,))
        return c.fetchone()
    
    def get_cycle_stats(self):
        c = self.conn.cursor()
        c.execute('''
            SELECT 
                AVG(cycle_length) as avg_cycle_length,
                AVG(period_length) as avg_period_length,
                COUNT(*) as total_cycles,
                MIN(start_date) as first_record,
                MAX(start_date) as last_record
            FROM cycles 
            WHERE cycle_length IS NOT NULL
        ''')
        return c.fetchone()
    
    def predict_next_period(self):
        cycles = self.get_cycles(6)  # Get last 6 cycles for prediction
        if len(cycles) < 2:
            return None, "Need more cycle data for accurate prediction"
        
        cycle_lengths = [cycle[3] for cycle in cycles if cycle[3] is not None]
        if not cycle_lengths:
            return None, "No cycle length data available"
        
        avg_cycle_length = sum(cycle_lengths) / len(cycle_lengths)
        last_cycle_start = datetime.strptime(cycles[0][1], '%Y-%m-%d')
        next_predicted_start = last_cycle_start + timedelta(days=avg_cycle_length)
        
        return next_predicted_start, f"Based on {len(cycle_lengths)} cycles, average {avg_cycle_length:.1f} days"

# Chart functions
def create_cycle_length_chart(cycles):
    """Create histogram of cycle lengths"""
    cycle_lengths = [cycle[3] for cycle in cycles if cycle[3] is not None]
    if not cycle_lengths:
        return None
    
    fig = px.histogram(
        x=cycle_lengths, 
        nbins=10, 
        title="Cycle Length Distribution",
        labels={'x': 'Cycle Length (days)', 'y': 'Frequency'},
        color_discrete_sequence=['#ff69b4']
    )
    return fig

def create_symptoms_chart(cycles):
    """Create pie chart of symptoms"""
    all_symptoms = []
    for cycle in cycles:
        if cycle[5]:
            symptoms = json.loads(cycle[5])
            all_symptoms.extend(symptoms)
    
    if not all_symptoms:
        return None
    
    symptom_counts = pd.Series(all_symptoms).value_counts()
    fig = px.pie(
        values=symptom_counts.values, 
        names=symptom_counts.index,
        title="Most Common Symptoms",
        color_discrete_sequence=px.colors.sequential.RdBu
    )
    return fig

def create_timeline_chart(cycles):
    """Create timeline of cycles"""
    if not cycles:
        return None
    
    cycle_data = []
    for cycle in cycles:
        cycle_data.append({
            'Start': cycle[1],
            'End': cycle[2],
            'Cycle Length': cycle[3] or 0,
            'Period Length': cycle[4] or 0
        })
    
    df = pd.DataFrame(cycle_data)
    fig = px.timeline(
        df, 
        x_start="Start", 
        x_end="End", 
        y=[1] * len(df),
        title="Cycle Timeline",
        color="Cycle Length",
        color_continuous_scale='viridis'
    )
    fig.update_yaxes(visible=False)
    fig.update_layout(height=300)
    return fig

# Page functions
def show_dashboard():
    st.markdown('<div class="section-header"><h2>📊 Dashboard Overview</h2></div>', unsafe_allow_html=True)
    
    tracker = PeriodTracker()
    
    col1, col2, col3 = st.columns(3)
    
    # Get stats
    stats = tracker.get_cycle_stats()
    cycles = tracker.get_cycles(5)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Total Cycles Recorded", stats[2] if stats else 0)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        avg_cycle = stats[0] if stats and stats[0] else "N/A"
        if isinstance(avg_cycle, float):
            st.metric("Average Cycle Length", f"{avg_cycle:.1f} days")
        else:
            st.metric("Average Cycle Length", avg_cycle)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        avg_period = stats[1] if stats and stats[1] else "N/A"
        if isinstance(avg_period, float):
            st.metric("Average Period Length", f"{avg_period:.1f} days")
        else:
            st.metric("Average Period Length", avg_period)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Recent cycles
    st.markdown('<div class="section-header"><h3>📅 Recent Cycles</h3></div>', unsafe_allow_html=True)
    if cycles:
        cycle_data = []
        for cycle in cycles:
            cycle_data.append({
                'Start Date': cycle[1],
                'End Date': cycle[2],
                'Cycle Length': cycle[3] or 'N/A',
                'Period Length': cycle[4] or 'N/A',
                'Mood': cycle[6] or 'N/A'
            })
        df = pd.DataFrame(cycle_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No cycles recorded yet. Go to 'Log Period' to add your first cycle!")
    
    # Quick log section
    st.markdown('<div class="section-header"><h3>⚡ Quick Log</h3></div>', unsafe_allow_html=True)
    with st.form("quick_log"):
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Period Start Date", datetime.now())
        with col2:
            end_date = st.date_input("Period End Date", datetime.now())
        
        if st.form_submit_button("📝 Log Period"):
            if start_date > end_date:
                st.error("End date cannot be before start date!")
            else:
                tracker.add_cycle(
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )
                st.success("Period logged successfully!")
                st.rerun()

def log_period():
    st.markdown('<div class="section-header"><h2>📝 Log New Period</h2></div>', unsafe_allow_html=True)
    
    tracker = PeriodTracker()
    
    with st.form("log_period_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.date_input("Start Date*", datetime.now())
            flow_level = st.selectbox("Flow Level", ["Light", "Medium", "Heavy", "Very Heavy"])
            mood = st.selectbox("Overall Mood", ["😊 Happy", "😐 Neutral", "😔 Sad", "😠 Irritated", "😌 Relaxed", "😫 Stressed"])
        
        with col2:
            end_date = st.date_input("End Date*", datetime.now() + timedelta(days=5))
            symptoms = st.multiselect("Symptoms", [
                "Cramps", "Bloating", "Headache", "Back Pain", 
                "Fatigue", "Food Cravings", "Breast Tenderness",
                "Acne", "Mood Swings", "Insomnia", "Nausea", "Anxiety"
            ])
        
        notes = st.text_area("Additional Notes", placeholder="Any additional observations...")
        
        submitted = st.form_submit_button("💾 Save Period")
        
        if submitted:
            if start_date > end_date:
                st.error("❌ End date cannot be before start date!")
            else:
                cycle_id = tracker.add_cycle(
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    symptoms=symptoms,
                    mood=mood,
                    flow_level=flow_level,
                    notes=notes
                )
                st.success(f"✅ Period logged successfully! Cycle ID: {cycle_id}")

def show_history():
    st.markdown('<div class="section-header"><h2>📋 Cycle History</h2></div>', unsafe_allow_html=True)
    
    tracker = PeriodTracker()
    
    cycles = tracker.get_cycles()
    
    if cycles:
        # Create DataFrame for display
        cycle_data = []
        for cycle in cycles:
            cycle_data.append({
                'ID': cycle[0],
                'Start Date': cycle[1],
                'End Date': cycle[2],
                'Cycle Length': cycle[3] or 'N/A',
                'Period Length': cycle[4] or 'N/A',
                'Symptoms': ', '.join(json.loads(cycle[5])) if cycle[5] else 'None',
                'Mood': cycle[6] or 'N/A',
                'Flow': cycle[7] or 'N/A',
                'Notes': cycle[8] or 'None'
            })
        
        df = pd.DataFrame(cycle_data)
        st.dataframe(df, use_container_width=True)
        
        # Export option
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("📤 Export to CSV"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="💾 Download CSV",
                    data=csv,
                    file_name="period_tracker_data.csv",
                    mime="text/csv"
                )
    else:
        st.info("No cycle history available. Start by logging your first period!")

def show_statistics():
    st.markdown('<div class="section-header"><h2>📈 Cycle Statistics</h2></div>', unsafe_allow_html=True)
    
    tracker = PeriodTracker()
    
    stats = tracker.get_cycle_stats()
    cycles = tracker.get_cycles()
    
    if not cycles:
        st.info("No data available for statistics. Log some periods first!")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.subheader("📊 Overview")
        if stats:
            st.write(f"**Total Cycles:** {stats[2]}")
            st.write(f"**Average Cycle Length:** {stats[0]:.1f} days" if stats[0] else "**Average Cycle Length:** N/A")
            st.write(f"**Average Period Length:** {stats[1]:.1f} days" if stats[1] else "**Average Period Length:** N/A")
            st.write(f"**Tracking Since:** {stats[3][:10]}" if stats[3] else "**Tracking Since:** N/A")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.subheader("📅 Cycle Length Distribution")
        chart = create_cycle_length_chart(cycles)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("No cycle length data available")
    
    # Symptoms analysis
    st.markdown('<div class="section-header"><h3>🤒 Symptoms Analysis</h3></div>', unsafe_allow_html=True)
    symptoms_chart = create_symptoms_chart(cycles)
    if symptoms_chart:
        st.plotly_chart(symptoms_chart, use_container_width=True)
    else:
        st.info("No symptoms data recorded")
    
    # Timeline
    st.markdown('<div class="section-header"><h3>⏰ Cycle Timeline</h3></div>', unsafe_allow_html=True)
    timeline_chart = create_timeline_chart(cycles)
    if timeline_chart:
        st.plotly_chart(timeline_chart, use_container_width=True)
    else:
        st.info("Not enough data for timeline")

def show_predictions():
    st.markdown('<div class="section-header"><h2>🔮 Period Predictions</h2></div>', unsafe_allow_html=True)
    
    tracker = PeriodTracker()
    
    st.markdown('<div class="prediction-card">', unsafe_allow_html=True)
    
    next_period, message = tracker.predict_next_period()
    
    if next_period:
        today = datetime.now().date()
        days_until = (next_period.date() - today).days
        
        st.subheader("🎯 Next Predicted Period")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Predicted Start", next_period.strftime('%B %d, %Y'))
        with col2:
            st.metric("Days Until", days_until)
        with col3:
            if days_until <= 7:
                st.metric("Status", "Approaching Soon", delta="7 days or less")
            else:
                st.metric("Status", "In Progress", delta=f"{days_until} days")
        
        st.info(f"📊 {message}")
        
        # Calendar view
        st.subheader("📅 Calendar View")
        display_calendar_with_prediction(next_period)
        
    else:
        st.warning(message)
        st.info("Log at least 2 complete cycles to get accurate predictions!")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Fertility window prediction
    st.markdown('<div class="section-header"><h3>👶 Fertility Window</h3></div>', unsafe_allow_html=True)
    st.info("Based on typical ovulation occurring 14 days before next period")
    
    if next_period:
        ovulation_date = next_period - timedelta(days=14)
        fertility_start = ovulation_date - timedelta(days=5)
        fertility_end = ovulation_date + timedelta(days=1)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.write("**Fertility Window:**")
            st.write(f"📅 {fertility_start.strftime('%b %d')} - {fertility_end.strftime('%b %d, %Y')}")
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.write("**Expected Ovulation:**")
            st.write(f"🥚 {ovulation_date.strftime('%B %d, %Y')}")
            st.markdown('</div>', unsafe_allow_html=True)

def display_calendar_with_prediction(next_period):
    # Create a calendar for the prediction month
    year = next_period.year
    month = next_period.month
    
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
    
    # Create calendar display
    st.write(f"### {month_name} {year}")
    
    # Calendar headers
    cols = st.columns(7)
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for i, day in enumerate(days):
        cols[i].write(f"**{day}**")
    
    # Calendar days
    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].write("")
            else:
                current_date = datetime(year, month, day).date()
                if current_date == next_period.date():
                    cols[i].markdown(f"<div style='background-color: #ff69b4; color: white; border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;'>{day}</div>", unsafe_allow_html=True)
                elif current_date == datetime.now().date():
                    cols[i].markdown(f"<div style='background-color: #90ee90; border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;'>{day}</div>", unsafe_allow_html=True)
                else:
                    cols[i].write(str(day))

# Main app
def main():
    # Initialize database
    init_db()
    
    st.markdown('<h1 class="main-header">🌸 Period Tracker</h1>', unsafe_allow_html=True)
    
    # Sidebar navigation
    st.sidebar.title("🧭 Navigation")
    page = st.sidebar.radio("Go to", [
        "📊 Dashboard", 
        "📝 Log Period", 
        "📋 Cycle History", 
        "📈 Statistics", 
        "🔮 Predictions"
    ])
    
    # Remove emojis for routing
    page_clean = page.replace("📊", "").replace("📝", "").replace("📋", "").replace("📈", "").replace("🔮", "").strip()
    
    # Route to appropriate page
    if page_clean == "Dashboard":
        show_dashboard()
    elif page_clean == "Log Period":
        log_period()
    elif page_clean == "Cycle History":
        show_history()
    elif page_clean == "Statistics":
        show_statistics()
    elif page_clean == "Predictions":
        show_predictions()
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.info(
        "Period Tracker helps you monitor your menstrual cycle, "
        "track symptoms, and predict future periods."
    )

if __name__ == "__main__":
    main()