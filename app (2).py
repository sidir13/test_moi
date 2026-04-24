import streamlit as st
import json

st.set_page_config(layout="wide")

st.title("Knowledge Graph")

with open("graph.json") as f:
    graph = json.load(f)

with open("graph.html") as f:
    html = f.read()

html = html.replace("__GRAPH_DATA__", json.dumps(graph))

st.components.v1.html(html, height=900)