import { api } from './client'
import type { AuthUser } from '../auth'
export interface PermissionItem { code:string; name:string }
export interface UserPayload { username?:string; display_name:string; password?:string; role:string; status?:string; permission_codes:string[] }
export const userApi={
  list:()=>api<AuthUser[]>('/users'),
  permissions:()=>api<PermissionItem[]>('/users/permissions'),
  create:(data:UserPayload)=>api<AuthUser>('/users',{method:'POST',body:JSON.stringify(data)}),
  update:(id:string,data:UserPayload)=>api<AuthUser>(`/users/${id}`,{method:'PUT',body:JSON.stringify(data)}),
  resetPassword:(id:string,password:string)=>api<AuthUser>(`/users/${id}/reset-password`,{method:'POST',body:JSON.stringify({password})}),
}
