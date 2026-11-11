#include <jni.h>
#include <dlfcn.h>
JNIEXPORT jstring JNICALL Java_com_cbr_nativetest_MainActivity_startEngine(JNIEnv* env, jobject self, jstring library, jstring data) {
 const char* path=(*env)->GetStringUTFChars(env,library,0);
 void* handle=dlopen(path,RTLD_NOW|RTLD_LOCAL);
 (*env)->ReleaseStringUTFChars(env,library,path);
 if(!handle) return (*env)->NewStringUTF(env,dlerror());
 int (*start)(int,const char*,char*,int)=dlsym(handle,"CBRStart");
 if(!start) return (*env)->NewStringUTF(env,"CBRStart export missing");
 const char* directory=(*env)->GetStringUTFChars(env,data,0);
 char error[2048]={0}; int result=start(8767,directory,error,sizeof(error));
 (*env)->ReleaseStringUTFChars(env,data,directory);
 return (*env)->NewStringUTF(env,result?error:"CBR embedded engine ready");
}
