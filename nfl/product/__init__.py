"""The product layer: reads frozen V1 output, renders it, and scores it.

NOTHING HERE MAY COMPUTE A FORECAST. Every number this package shows is read
from a sealed artifact and its draw sidecar, or is a function of those draws
alone. It holds no estimator, no prior and no parameter, and it never imports
a model layer to run one.
"""
