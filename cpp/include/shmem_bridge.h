#pragma once
// VOIDFORGE AFL++ shared-memory coverage bridge — Linux/WSL only.
// Attaches to AFL++'s __AFL_SHM_ID bitmap so the C++ side can read
// fork-server coverage without any Python involvement.
#include "common.h"

#ifdef __linux__
#include <sys/shm.h>
#include <cstdlib>
#include <cstring>

namespace vf {

// Read AFL++'s shared memory coverage bitmap
// AFL++ sets __AFL_SHM_ID env var with the shmid
class AflShmBridge {
public:
    bool attach() {
        const char* id_str = std::getenv("__AFL_SHM_ID");
        if (!id_str) return false;
        int shmid = std::atoi(id_str);
        void* ptr = shmat(shmid, nullptr, 0);
        if (ptr == (void*)-1) return false;
        shm_ptr_ = static_cast<uint8_t*>(ptr);
        return true;
    }

    void detach() {
        if (shm_ptr_) { shmdt(shm_ptr_); shm_ptr_ = nullptr; }
    }

    // Copy current bitmap to our Bitmap struct
    Bitmap snapshot() const {
        Bitmap bm{};
        if (shm_ptr_) std::memcpy(bm.data(), shm_ptr_, BITMAP_SIZE);
        return bm;
    }

    // Direct pointer (for in-process use)
    uint8_t* raw() { return shm_ptr_; }

private:
    uint8_t* shm_ptr_ = nullptr;
};

} // namespace vf
#endif // __linux__
