"""Fill the app with demo data so you can try every feature in 1 minute.

   python scripts/seed_demo.py

Creates (password for all: demo1234):
   ananya@demo.com  - job seeker (data analyst resume, auto-apply ON)
   rahul@demo.com   - job seeker (ROS engineer resume)
   fathima@demo.com - job seeker (fresher Python developer)
   hr@demo.com      - recruiter at 'Demo Analytics Pvt Ltd' with one posted job
and loads the sample jobs. Resume files must be in the data folder.
"""
import _path  # noqa: F401
from sja.demo import seed

if __name__ == "__main__":
    seed()
    print("\nDone. Run:  streamlit run app.py   and log in with any account above (password demo1234).")
