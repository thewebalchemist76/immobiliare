"""Configuration for Immobiliare.it scraper filters"""

# Property types mapping
PROPERTY_TYPES = {
    'appartamento': '1',
    'villa': '2',
    'rustico': '43',
    # Add more as needed
}

# Property condition mapping
PROPERTY_CONDITION = {
    'nuovo': '1',
    'ottimo': '6',
    'buono': '2',
    'da_ristrutturare': '5'
}

# Floor types
FLOOR_TYPES = {
    'terra': '10',
    'intermedi': '20',
    'ultimo': '30'
}

# Garage types
GARAGE_TYPES = {
    'singolo': '1',
    'doppio': '3',
    'posto_auto': '4'
}

# Heating types
HEATING_TYPES = {
    'autonomo': '1',
    'centralizzato': '2'
}

# Garden types
GARDEN_TYPES = {
    'privato': '10',
    'comune': '20'
}

# Energy efficiency
ENERGY_EFFICIENCY = {
    'alta': 'high',
    'media': 'medium',
    'bassa': 'low',
    'tutte': 'all'
}