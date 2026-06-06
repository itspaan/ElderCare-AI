import pandas as pd
import numpy as np
import random
import os

# Mengunci random state agar datanya tetap sama setiap kali di-generate
np.random.seed(42)
random.seed(42)

num_samples = 2000
data = []

for _ in range(num_samples):
    age = random.randint(60, 95)
    
    # Probabilitas pembagian penyakit
    disease_type = random.choices(
        ['Hypertension', 'Diabetes', 'Osteoarthritis', 'Dementia', 'Healthy'],
        weights=[0.3, 0.25, 0.2, 0.1, 0.15]
    )[0]
    
    # Setup default values
    systolic_bp = random.randint(110, 130) # Normal
    blood_sugar = random.randint(70, 110)  # Normal
    joint_pain = 0
    memory_loss = 0
    fatigue = random.choice([0, 1])

    # Sesuaikan gejala/tanda vital berdasarkan penyakitnya
    if disease_type == 'Hypertension':
        systolic_bp = random.randint(140, 180)
        fatigue = random.choice([0, 1])
        
    elif disease_type == 'Diabetes':
        blood_sugar = random.randint(126, 250)
        fatigue = 1
        
    elif disease_type == 'Osteoarthritis':
        joint_pain = 1
        
    elif disease_type == 'Dementia':
        memory_loss = 1
        age = random.randint(70, 95) # Demensia biasanya di usia lebih tua
        
    elif disease_type == 'Healthy':
        fatigue = 0

    data.append([age, systolic_bp, blood_sugar, joint_pain, memory_loss, fatigue, disease_type])

# Buat DataFrame dan simpan ke CSV
columns = ['Age', 'Systolic_BP', 'Blood_Sugar', 'Joint_Pain', 'Memory_Loss', 'Fatigue', 'Disease']
df = pd.DataFrame(data, columns=columns)

# Save to data/ directory (same directory as this script)
output_path = os.path.join(os.path.dirname(__file__), 'elderly_synthetic_data.csv')
df.to_csv(output_path, index=False)
print(f"Sukses! {len(df)} baris data telah disimpan di '{output_path}'")
print(df.head())
