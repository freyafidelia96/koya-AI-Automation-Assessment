import streamlit as st
import pandas as pd
import numpy as np

# --- 1. Data Cleaning Functions ---

def clean_budget(b):
    """Parses messy string budgets into clean float values."""
    if pd.isna(b): return np.nan
    b = str(b).lower().replace('$', '').replace(',', '').replace('/mo', '').replace('+', '').replace('~', '').strip()
    if b in ['tbd', 'budget', 'asdf', 'depends', 'nan', '']: return np.nan
    
    if '-' in b: 
        b = b.split('-')[-1] # Take upper bound of range
        
    if 'k' in b:
        try: return float(b.replace('k', '')) * 1000
        except: pass
        
    try: return float(b)
    except: return np.nan

def clean_employees(e):
    """Parses messy string employee counts into clean floats."""
    if pd.isna(e): return np.nan
    e = str(e).lower().replace(',', '').replace('+', '').replace('~', '').strip()
    
    if '-' in e:
        parts = e.split('-')
        try: return (int(parts[0]) + int(parts[1])) / 2 # Take average of range
        except: return np.nan
        
    try: return float(e)
    except: return np.nan

# --- 2. The Core Scoring Engine ---

def calculate_score(row):
    """Calculates a lead's score based on the agreed rubric."""
    score = 0
    
    # Title/Role (+50 / -50)
    title = str(row.get('title', '')).lower()
    high_titles = ['vp', 'head of', 'founder', 'ceo', 'managing partner', 'coo', 'owner', 'director', 'cto']
    low_titles = ['student', 'intern', 'freelancer', 'developer']
    
    if any(t in title for t in high_titles):
        score += 50
    elif any(t in title for t in low_titles):
        score -= 50
        
    # Source (+10 for Referral)
    source = str(row.get('source', '')).lower().strip()
    if source == 'referral':
        score += 10
        
    # Monthly Budget (+30 / +15)
    budget = clean_budget(row.get('monthly_budget'))
    if pd.notna(budget):
        if budget >= 8000:
            score += 30
        elif 5000 <= budget < 8000:
            score += 15
            
    # Employees (+20 / +10)
    emps = clean_employees(row.get('employees'))
    if pd.notna(emps):
        if emps >= 26:
            score += 20
        elif 10 <= emps <= 25:
            score += 10
            
    # Notes (+15 / -20 / -100)
    notes = str(row.get('notes', '')).lower()
    
    high_intent = ['budget approved', 'urgent', 'ready', 'decision maker', 'timeline', 'asap', 'budgeted', 'have some budget']
    low_intent = ['researching', 'budget not locked', 'price sensitive', 'no real budget', 'scale']
    instant_disqualifiers = [
        'not looking to buy', 'developer', 'cv', 'resume', 'student', 
        'not a direct buyer', 'journalist', 'qa', "can't really pay", 
        'not a buyer', 'budget way below range', 'ignore this', 
        'test entry', 'mistake', 'sell', 'not a client', 'mentorship', 
        'followers and likes', 'place candidates', 'fellow agency', 'offering'
    ]
    
    if any(word in notes for word in instant_disqualifiers):
        score -= 100
    else:
        if any(word in notes for word in high_intent): score += 15
        if any(word in notes for word in low_intent): score -= 20
            
    return score

# --- 3. Categorization ---

def categorize_lead(score):
    """Buckets leads into Contact Now, Nurture, or Disqualified."""
    if score >= 70:
        return 'Contact Now 🔥'
    elif score > 0:
        return 'Nurture 🌱'
    else:
        return 'Disqualified ❌'

# --- 4. Streamlit UI Interface ---

st.set_page_config(page_title="Lead Qualifier", layout="wide")
st.title("🚀 Automated Lead Qualification System")
st.markdown("Upload your lead export to automatically clean, score, and prioritize leads based on role, budget, company size, and intent signals.")

uploaded_file = st.file_uploader("Upload Lead CSV", type=['csv'])

if uploaded_file is not None:
    raw_df = pd.read_csv(uploaded_file)
    
    with st.spinner("Scoring leads..."):
        df = raw_df.copy()
        
        # 1. Calculate Base Score
        df['lead_score'] = df.apply(calculate_score, axis=1)
        
        # 2. Handle Hidden Duplicates
        if 'email' in df.columns:
            has_email = df['email'].notna() & (df['email'] != '')
            
            # We sort the dataframe first so rows WITH the text "(duplicate submission)" 
            # get pushed to the bottom. This ensures Pandas keeps the clean, authentic version!
            df['is_explicit_dupe'] = df['notes'].astype(str).str.contains('duplicate submission', case=False)
            df = df.sort_values(by='is_explicit_dupe') 
            
            # Now we apply the Pandas duplicate check
            is_duplicate = df.duplicated(subset=['email'], keep='first')
            df.loc[is_duplicate & has_email, 'lead_score'] -= 125
            
            # Clean up our temporary sorting column
            df = df.drop(columns=['is_explicit_dupe'])
            
        # 3. Categorize based on Final Score
        df['recommendation'] = df['lead_score'].apply(categorize_lead)
        
        # 4. Sort highest scores to the top
        df = df.sort_values(by='lead_score', ascending=False)
        
    st.subheader("📊 Qualification Results")
    
    # Calculate Metrics
    contact_now = len(df[df['recommendation'] == 'Contact Now 🔥'])
    nurture = len(df[df['recommendation'] == 'Nurture 🌱'])
    disqualified = len(df[df['recommendation'] == 'Disqualified ❌'])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Contact Now 🔥", contact_now)
    col2.metric("Nurture 🌱", nurture)
    col3.metric("Disqualified ❌", disqualified)
    
    # Data Preview
    st.dataframe(df[['name', 'email', 'company', 'title', 'lead_score', 'recommendation', 'notes']].head(50))
    
    # Export Button
    csv_export = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Processed Leads (CSV)",
        data=csv_export,
        file_name='qualified_leads_export.csv',
        mime='text/csv',
    )