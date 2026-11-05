import {proxySimulation} from "@/lib/simulation-proxy";
export const dynamic="force-dynamic";
export const runtime="nodejs";
async function handle(request:Request,context:{params:Promise<{path:string[]}>}){const {path}=await context.params;return proxySimulation(request,path);}
export const GET=handle;
export const POST=handle;
