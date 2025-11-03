#!/usr/bin/env python3
import json, random
from pathlib import Path

def generate_transaction_data_realistic(n_accounts=40, n_transactions=600):
    accounts = [f"KONTO_{i:03d}" for i in range(n_accounts)]
    txs = []
    n_hubs = max(2, n_accounts // 6)
    hubs = random.sample(accounts, n_hubs)

    for _ in range(n_transactions):
        if random.random() < 0.4:
            src = random.choice(hubs)
        else:
            src = random.choice(accounts)
        possible_targets = [a for a in accounts if a != src]
        if src in hubs:
            tgt = random.choice(possible_targets)
        else:
            tgt = random.choice(hubs + random.sample(possible_targets, k=min(2, len(possible_targets))))
        amount = round(random.paretovariate(1.5) * 200, 2)
        txs.append({"source": src, "target": tgt, "amount": amount})

    agg = {}
    for t in txs:
        key = (t["source"], t["target"])
        if key not in agg:
            agg[key] = {"count": 0, "sum": 0.0}
        agg[key]["count"] += 1
        agg[key]["sum"] += t["amount"]

    nodes = [{"id": a, "is_hub": a in hubs} for a in accounts]
    links = [{"source": s, "target": t, "count": v["count"], "sum": v["sum"]} for (s, t), v in agg.items()]
    return {"nodes": nodes, "links": links}


def build_html(data, output_path="transaction_graph_table.html"):
    data_json = json.dumps(data)
    html = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8"/>
<title>Graf transakcji z tabelą</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  html,body{height:100%;margin:0;background:#071022;color:#e6eef8;font-family:Inter,Segoe UI,Arial}
  svg{width:100%;height:100%;display:block}
  .link{stroke:rgba(56,189,248,0.6);fill:none}
  .edge-label{font-size:10px;fill:#a5d8ff;pointer-events:none;text-anchor:middle}
  .node circle{stroke:#0b1220;stroke-width:1.2px;cursor:grab}
  text.label{font-size:11px;pointer-events:none;fill:#cfe8ff}
  #tooltip{position:absolute;pointer-events:none;padding:8px;border-radius:6px;background:rgba(2,6,23,0.88);color:#dbeefe;font-size:13px;box-shadow:0 6px 18px rgba(0,0,0,0.6)}
  header.ui{position:absolute;left:12px;top:12px;z-index:10;background:rgba(255,255,255,0.02);padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.03)}
  input,button{padding:4px 8px;border-radius:4px;border:none;font-size:13px}
  button{background:#2563eb;color:white;cursor:pointer}
  button:hover{background:#1e40af}
  table{margin-top:10px;border-collapse:collapse;width:100%;font-size:13px;color:#d8e0f0}
  th,td{border-bottom:1px solid rgba(255,255,255,0.1);padding:4px 8px;text-align:left}
  #tableContainer{position:absolute;right:12px;top:12px;z-index:10;width:300px;background:rgba(255,255,255,0.04);border-radius:8px;padding:10px;overflow:auto;max-height:90%}
</style>
</head>
<body>
<header class="ui">
  <strong>Graf transakcji</strong><br>
  <small>Kliknij w konto lub wpisz numer, aby zobaczyć jego transakcje.</small><br>
  <input id="accountInput" placeholder="np. KONTO_005"/>
  <button id="showTableBtn">Pokaż transakcje</button>
  <label><input type="checkbox" id="showEdgeLabels" checked> Pokaż etykiety przepływów</label>
</header>

<div id="tableContainer"></div>
<div id="tooltip" style="opacity:0;"></div>
<svg></svg>

<script>
const fullGraph = __DATA__;
let graph = JSON.parse(JSON.stringify(fullGraph));

const svg = d3.select("svg");
const width = window.innerWidth, height = window.innerHeight;
const g = svg.append("g");

svg.call(d3.zoom().scaleExtent([0.2,8]).on("zoom", e=>g.attr("transform",e.transform)));

const defs = svg.append("defs");
defs.append("marker")
  .attr("id","arrow").attr("viewBox","0 -5 10 10")
  .attr("refX",18).attr("refY",0)
  .attr("markerWidth",8).attr("markerHeight",8).attr("orient","auto")
  .append("path").attr("d","M0,-5L10,0L0,5").attr("fill","rgba(56,189,248,0.9)");

const tooltip = d3.select("#tooltip");
const tableContainer = d3.select("#tableContainer");

let link, node, edgeLabel;
let simulation = d3.forceSimulation()
  .force("link", d3.forceLink().id(d=>d.id).distance(d=>100+Math.log1p(d.sum||1)*15))
  .force("charge", d3.forceManyBody().strength(-300))
  .force("center", d3.forceCenter(width/2,height/2))
  .force("collide", d3.forceCollide(14));

function updateGraph(){
  g.selectAll("*").remove();

  link = g.append("g").selectAll("path").data(graph.links).enter()
    .append("path").attr("class","link")
    .attr("stroke-width",d=>Math.max(1,Math.sqrt(d.sum)/20))
    .attr("marker-end","url(#arrow)");

  if (document.getElementById("showEdgeLabels").checked){
    edgeLabel = g.append("g").selectAll("text").data(graph.links).enter()
      .append("text").attr("class","edge-label")
      .text(d=>d.sum.toFixed(0)+" zł");
  }

  node = g.append("g").selectAll("g").data(graph.nodes).enter().append("g").attr("class","node")
    .on("click",(event,d)=>showTable(d.id))
    .call(drag(simulation));

  node.append("circle").attr("r",d=>d.is_hub?10:6).attr("fill",d=>d.is_hub?"#38bdf8":"#93c5fd");
  node.append("text").attr("class","label").attr("x",12).attr("y",4).text(d=>d.id);

  node.on("mouseover",(e,d)=>{
    tooltip.style("opacity",1).html("<strong>"+d.id+"</strong><br>"+(d.is_hub?"Hub (aktywny)":"Zwykły rachunek"));
  }).on("mousemove",e=>{
    tooltip.style("left",(e.pageX+12)+"px").style("top",(e.pageY+12)+"px");
  }).on("mouseout",()=>tooltip.style("opacity",0));

  link.on("mouseover",(e,d)=>{
    tooltip.style("opacity",1).html("<strong>"+d.source.id+"</strong> → <strong>"+d.target.id+"</strong><br>Transakcji: "+d.count+"<br>Suma: "+d.sum.toFixed(2)+" zł");
  }).on("mousemove",e=>{
    tooltip.style("left",(e.pageX+12)+"px").style("top",(e.pageY+12)+"px");
  }).on("mouseout",()=>tooltip.style("opacity",0));

  simulation.nodes(graph.nodes).on("tick",ticked);
  simulation.force("link").links(graph.links);
  simulation.alpha(1).restart();
}

function ticked(){
  link.attr("d",d=>{
    const sx=d.source.x,sy=d.source.y,tx=d.target.x,ty=d.target.y;
    const dx=tx-sx,dy=ty-sy,mx=(sx+tx)/2,my=(sy+ty)/2;
    const norm=Math.sqrt(dx*dx+dy*dy)||1,offset=Math.min(80,100/(1+Math.log1p(d.sum||1)));
    const cx=mx-dy/norm*offset,cy=my+dx/norm*offset;
    return "M"+sx+","+sy+" Q"+cx+","+cy+" "+tx+","+ty;
  });
  node.attr("transform",d=>"translate("+d.x+","+d.y+")");
  if (edgeLabel) edgeLabel.attr("x",d=>{
      const midX=(d.source.x+d.target.x)/2,dy=d.target.y-d.source.y;
      return midX + (dy>0?6:-6);
    }).attr("y",d=>{
      const midY=(d.source.y+d.target.y)/2,dx=d.target.x-d.source.x;
      return midY - (dx>0?6:-6);
    });
}

function drag(sim){
  function started(e,d){if(!e.active)sim.alphaTarget(0.25).restart();d.fx=d.x;d.fy=d.y;}
  function dragged(e,d){d.fx=e.x;d.fy=e.y;}
  function ended(e,d){if(!e.active)sim.alphaTarget(0);}
  return d3.drag().on("start",started).on("drag",dragged).on("end",ended);
}

function showTable(accountId){
  const relevant=fullGraph.links.filter(l=>l.source===accountId||l.target===accountId);
  if(relevant.length===0){tableContainer.html("<h3>"+accountId+"</h3><p>Brak transakcji.</p>");return;}
  let html="<h3>"+accountId+"</h3><table><thead><tr><th>Nadawca</th><th>Odbiorca</th><th>Liczba</th><th>Suma</th></tr></thead><tbody>";
  relevant.forEach(r=>{
    html+="<tr><td>"+r.source+"</td><td>"+r.target+"</td><td>"+r.count+"</td><td>"+r.sum.toFixed(2)+" zł</td></tr>";
  });
  html+="</tbody></table>";
  tableContainer.html(html);
}

document.getElementById("showTableBtn").onclick=()=>{
  const input=document.getElementById("accountInput").value.trim();
  if(input) showTable(input);
};
document.getElementById("showEdgeLabels").onchange=updateGraph;

updateGraph();
</script>
</body>
</html>"""
    html = html.replace("__DATA__", data_json)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"✅ Wygenerowano: {output_path}")


if __name__ == "__main__":
    data = generate_transaction_data_realistic(40, 700)
    build_html(data)
