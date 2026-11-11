/* Override only local driven vehicle inputs at the pinned physics boundary. */
#include "../../runtime/native/gameplay.h"
#include "input_core.h"
#include "../vehicle-control-framework/sdk/client.h"
static const MoonControls *controls;
int _fltused=0;
static PTR fields[6],owner_m,driven_m,blocked_m,menu_m,typing_m,focus_m,actions[3];
static void (*set_field)(PTR,PTR,void *);
static BOOL (*read_file)(PTR,void *,DWORD,DWORD *,PTR),(*close_file)(PTR);
static void (*system_time)(U64 *);
static PTR (*foreground)(void);
static DWORD (*window_pid)(PTR,DWORD *);
static char state_path[1024];
static PTR last_vehicle;
static unsigned int previous_buttons;
static int active;
static U64 last_read;
static float last_steer,last_throttle;
static unsigned char last_brake,last_boost;

static void input_fields(PTR vehicle,float steer,float throttle,unsigned char brake,unsigned char boost){
    set_field(vehicle,fields[0],&throttle);set_field(vehicle,fields[1],&steer);
    set_field(vehicle,fields[2],&brake);set_field(vehicle,fields[3],&boost);
    set_field(vehicle,fields[4],&steer);set_field(vehicle,fields[5],&steer);
}
static void release(PTR vehicle){
    /* Never dereference the remembered object: it may have been destroyed.
     * Only clean this live callback's object if our values still own its inputs.
     * A later vanilla Update then regains keyboard/controller control. */
    if(active && vehicle==last_vehicle){
        float t=0,s=0;unsigned char b=0,h=0;
        field_value(vehicle,fields[0],&t);field_value(vehicle,fields[1],&s);
        field_value(vehicle,fields[2],&b);field_value(vehicle,fields[3],&h);
        if(t==last_throttle && s==last_steer && b==last_brake && h==last_boost)
            input_fields(vehicle,0,0,0,0);
        active=0;previous_buttons=0;
    }
}
static int vehicle_before(int id,Context *c,MoonVehicleInput *input){
    if(input)input->valid=0;
    (void)id;PTR vehicle=(PTR)c->rcx;int ok=1;
    if(!boolean(driven_m,vehicle,&ok)||!ok){release(vehicle);return 0;}
    PTR owner=call(owner_m,vehicle,0,&ok);DWORD pid=0;
    window_pid(foreground(),&pid);
    if(!owner||!ok||pid!=GetCurrentProcessId()||!boolean(focus_m,0,&ok)||
       boolean(blocked_m,owner,&ok)||boolean(menu_m,owner,&ok)||boolean(typing_m,0,&ok)||!ok){
        release(vehicle);return 0;
    }
    WheelPacket packet;DWORD size=0;U64 now=0;
    PTR file=CreateFileA(state_path,0x80000000,7,0,3,0x80,0);
    if(file==(PTR)(U64)-1){release(vehicle);return 0;}
    int read_ok=read_file(file,&packet,sizeof(packet),&size,0);close_file(file);system_time(&now);
    if(!read_ok||size!=sizeof(packet)||!wheel_valid(&packet,now)){release(vehicle);return 0;}
    unsigned int edges=(active&&last_vehicle==vehicle&&now>=last_read&&now-last_read<=2500000)?packet.buttons&~previous_buttons:0;
    previous_buttons=packet.buttons;last_vehicle=vehicle;active=1;last_read=now;
    last_steer=packet.steer;last_throttle=packet.throttle;
    last_brake=(packet.buttons&1)!=0;last_boost=(packet.buttons&2)!=0;
    if(last_brake)last_throttle=0;
    input_fields(vehicle,last_steer,last_throttle,last_brake,last_boost);
    if(input){input->valid=1;input->steer=last_steer;input->throttle=last_throttle;input->brake=last_brake;input->boost=last_boost;}
    /* Actions run on the existing physics thread; initial/reconnected held
     * buttons are suppressed until released, including exit. */
    for(int i=0;i<3;i++)if(edges&(4u<<i))call(actions[i],vehicle,0,&ok);
    return 0;
}
static int before(int id,Context *c){return vehicle_before(id,c,0);}
static int wheel_propose(void *car,const MoonControlFrame *frame,MoonVehicleInput *input){
    (void)frame;Context c={0};c.rcx=(U64)car;return vehicle_before(0,&c,input);
}
int MoonLab_ModStart(PTR domain,PTR game){
    if(!bind_runtime(domain,game))return 0;
    PTR kernel=LoadLibraryA("kernel32.dll"),user=LoadLibraryA("user32.dll");
    if(!kernel||!user)return 0;
#define LOAD(VAR,LIB,NAME,TYPE) VAR=(TYPE)GetProcAddress(LIB,NAME);if(!VAR)return 0
    LOAD(set_field,game,"il2cpp_field_set_value",void(*)(PTR,PTR,void *));
    LOAD(read_file,kernel,"ReadFile",BOOL(*)(PTR,void *,DWORD,DWORD *,PTR));
    LOAD(close_file,kernel,"CloseHandle",BOOL(*)(PTR));
    LOAD(system_time,kernel,"GetSystemTimeAsFileTime",void(*)(U64 *));
    LOAD(foreground,user,"GetForegroundWindow",PTR(*)(void));
    LOAD(window_pid,user,"GetWindowThreadProcessId",DWORD(*)(PTR,DWORD *));
#undef LOAD
    DWORD n=GetEnvironmentVariableA("MOONLAB_WHEEL_STATE",state_path,sizeof(state_path));
    if(n>=sizeof(state_path))return 0;if(!n)cat(state_path,"MoonLab.Wheel.bin");
    PTR vehicle_class=find_class("MoonCleaners","MoonPrototypeVehicle");
    int (*offset)(PTR)=(int(*)(PTR))GetProcAddress(game,"il2cpp_field_get_offset");
    const char *names[]={"throttle","steer","brake","boost","<Steering>k__BackingField","airTurn"};
    const int offsets[]={280,284,301,303,116,472};
    if(!vehicle_class||!offset)return 0;
    for(int i=0;i<6;i++){fields[i]=get_field(vehicle_class,names[i]);if(!fields[i]||offset(fields[i])!=offsets[i])return 0;}
#define METHOD(VAR,CLASS,NAME) VAR=method("MoonCleaners",CLASS,NAME,0);if(!VAR)return 0
    METHOD(owner_m,"MoonPrototypeVehicle","get_Owner");
    METHOD(driven_m,"MoonPrototypeVehicle","get_IsDriven");
    METHOD(blocked_m,"MoonWalker","get_UIBlocked");METHOD(menu_m,"MoonWalker","get_MenuBlocked");
    METHOD(typing_m,"MoonInput","get_Typing");
    METHOD(actions[0],"MoonPrototypeVehicle","ToggleLights");
    METHOD(actions[1],"MoonPrototypeVehicle","ToggleCleaning");
    METHOD(actions[2],"MoonPrototypeVehicle","Exit");
#undef METHOD
    focus_m=method("UnityEngine","Application","get_isFocused",0);if(!focus_m)return 0;
    controls=mc_connect(domain,game);if(!controls)return 0;
    MoonControlProvider provider={MC_ABI,sizeof(provider),"wheel-control",MC_HARDWARE,100,wheel_propose};
    if(!controls->register_provider(&provider))return 0;
    (void)integer;(void)num;(void)before;(void)prepare_hook;(void)install_hooks;return 1;
}
