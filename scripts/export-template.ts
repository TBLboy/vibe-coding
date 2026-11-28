import {writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {getTemplate} from '../server/templates/registry.ts';
const pack=getTemplate('engineering-dev')!;
const output=JSON.stringify({...pack,sha256:createHash('sha256').update(JSON.stringify({type:pack.type,version:pack.version,files:pack.files})).digest('hex')},null,2)+'\n';
if(process.argv[2])writeFileSync(process.argv[2],output);else process.stdout.write(output);
