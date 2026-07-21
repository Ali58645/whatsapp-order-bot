import{c as o,r as n,a as f,j as t,L as g,d as m}from"./index-DXOEM-oo.js";import{B as b}from"./badge-CEvsJcoa.js";/**
 * @license lucide-react v1.25.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const j=[["path",{d:"m9 18 6-6-6-6",key:"mthhwq"}]],_=o("chevron-right",j);/**
 * @license lucide-react v1.25.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const y=[["path",{d:"M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8",key:"1357e3"}],["path",{d:"M3 3v5h5",key:"1xhq8a"}]],w=o("rotate-ccw",y);/**
 * @license lucide-react v1.25.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const v=[["path",{d:"M10 11v6",key:"nco0om"}],["path",{d:"M14 11v6",key:"outv1u"}],["path",{d:"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6",key:"miytrc"}],["path",{d:"M3 6h18",key:"d0wm0j"}],["path",{d:"M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2",key:"e791ji"}]],L=o("trash-2",v),l={utensils:"🍽️","shopping-basket":"🛒",droplets:"💧",pill:"💊",cake:"🎂",shirt:"👕",scissors:"✂️",monitor:"💻","shopping-cart":"🛍️","message-circle":"💬",wrench:"🔧",smartphone:"📱",tv:"📺",beef:"🥩",carrot:"🥬",milk:"🥛",dumbbell:"🏋️",stethoscope:"🩺",car:"🚗","graduation-cap":"📚",home:"🏠",sparkles:"✨",flower:"💐",store:"🏪"};function C({selectedId:h,onSelect:p,flowMode:s,className:u}){const[r,i]=n.useState([]),[x,c]=n.useState(!0);n.useEffect(()=>{c(!0);const e=s?`?flow_mode=${s}`:"";f(`/api/dashboard/templates${e}`,{tenant:!1}).then(a=>i(a.items||[])).catch(()=>i([])).finally(()=>c(!1))},[s]);const d=n.useMemo(()=>{if(!s)return r;const e=r.filter(a=>a.flow_mode===s);return e.length?e:r},[r,s]);return x?t.jsxs("div",{className:"flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground",children:[t.jsx(g,{className:"h-4 w-4 animate-spin"}),"Loading templates…"]}):d.length?t.jsx("div",{className:m("grid max-h-[50vh] gap-2 overflow-y-auto sm:grid-cols-2",u),children:d.map(e=>{const a=l[e.icon||""]||l.store;return t.jsxs("button",{type:"button",onClick:()=>p(e.id,e),className:m("rounded-xl border px-3 py-3 text-left transition-colors",h===e.id?"border-primary bg-primary/10":"border-border hover:bg-muted/40"),children:[t.jsxs("div",{className:"flex items-start justify-between gap-2",children:[t.jsxs("div",{className:"flex items-center gap-2 min-w-0",children:[t.jsx("span",{className:"text-lg","aria-hidden":!0,children:a}),t.jsx("p",{className:"truncate text-sm font-semibold",children:e.name})]}),t.jsx(b,{className:"shrink-0 bg-muted text-muted-foreground text-[10px]",children:e.flow_mode})]}),t.jsx("p",{className:"mt-1.5 line-clamp-2 text-xs text-muted-foreground",children:e.blurb||e.description})]},e.id)})}):t.jsx("p",{className:"text-sm text-muted-foreground",children:"No templates found."})}export{_ as C,w as R,L as T,C as a};
