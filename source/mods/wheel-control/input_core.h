/* Wire format is little-endian, fixed-size and shared with wheel.py. */
#ifndef WHEEL_INPUT_CORE_H
#define WHEEL_INPUT_CORE_H
typedef struct {
    unsigned int magic,version;
    unsigned long long timestamp;
    float steer,throttle;
    unsigned int buttons,enabled;
} WheelPacket;
_Static_assert(sizeof(WheelPacket)==32,"wheel packet ABI");
static int wheel_valid(const WheelPacket *p,unsigned long long now){
    return p->magic==0x314c4857 && p->version==1 && p->enabled==1 &&
        p->timestamp<=now && now-p->timestamp<=2500000 &&
        p->steer>=-1 && p->steer<=1 && p->throttle>=-1 && p->throttle<=1 &&
        !(p->buttons&~31u);
}
#endif
